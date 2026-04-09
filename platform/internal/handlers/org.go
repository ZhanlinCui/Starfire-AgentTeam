package handlers

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"strings"

	"github.com/agent-molecule/platform/internal/crypto"
	"github.com/agent-molecule/platform/internal/db"
	"github.com/agent-molecule/platform/internal/events"
	"github.com/agent-molecule/platform/internal/models"
	"github.com/agent-molecule/platform/internal/provisioner"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
	"gopkg.in/yaml.v3"
)

// OrgHandler manages org template import/export.
type OrgHandler struct {
	workspace   *WorkspaceHandler
	broadcaster *events.Broadcaster
	provisioner *provisioner.Provisioner
	configsDir  string
	orgDir      string // path to org-templates/
}

func NewOrgHandler(wh *WorkspaceHandler, b *events.Broadcaster, p *provisioner.Provisioner, configsDir, orgDir string) *OrgHandler {
	return &OrgHandler{
		workspace:   wh,
		broadcaster: b,
		provisioner: p,
		configsDir:  configsDir,
		orgDir:      orgDir,
	}
}

// OrgTemplate is the YAML structure for an org hierarchy.
type OrgTemplate struct {
	Name        string            `yaml:"name"`
	Description string            `yaml:"description"`
	Defaults    OrgDefaults       `yaml:"defaults"`
	Workspaces  []OrgWorkspace    `yaml:"workspaces"`
}

type OrgDefaults struct {
	Runtime string   `yaml:"runtime"`
	Tier    int      `yaml:"tier"`
	Plugins []string `yaml:"plugins"`
}

type OrgWorkspace struct {
	Name         string         `yaml:"name"`
	Role         string         `yaml:"role"`
	Runtime      string         `yaml:"runtime"`
	Tier         int            `yaml:"tier"`
	Template     string         `yaml:"template"`
	FilesDir     string         `yaml:"files_dir"`      // folder name relative to org template dir
	SystemPrompt string         `yaml:"system_prompt"`  // inline (overridden by files_dir/system-prompt.md)
	Model        string         `yaml:"model"`
	WorkspaceDir string         `yaml:"workspace_dir"`  // host path to mount as /workspace (empty = isolated volume)
	Plugins      []string       `yaml:"plugins"`        // plugins to pre-install from registry
	External     bool           `yaml:"external"`
	URL          string         `yaml:"url"`
	Canvas       struct {
		X float64 `yaml:"x"`
		Y float64 `yaml:"y"`
	} `yaml:"canvas"`
	Children     []OrgWorkspace `yaml:"children"`
}

// ListTemplates handles GET /org/templates — lists available org templates.
func (h *OrgHandler) ListTemplates(c *gin.Context) {
	templates := []map[string]interface{}{}

	entries, err := os.ReadDir(h.orgDir)
	if err != nil {
		c.JSON(http.StatusOK, templates)
		return
	}

	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		// Look for org.yaml inside the directory
		orgFile := filepath.Join(h.orgDir, e.Name(), "org.yaml")
		data, err := os.ReadFile(orgFile)
		if err != nil {
			// Try org.yml
			orgFile = filepath.Join(h.orgDir, e.Name(), "org.yml")
			data, err = os.ReadFile(orgFile)
			if err != nil {
				continue
			}
		}
		var tmpl OrgTemplate
		if err := yaml.Unmarshal(data, &tmpl); err != nil {
			continue
		}
		count := countWorkspaces(tmpl.Workspaces)
		templates = append(templates, map[string]interface{}{
			"dir":         e.Name(),
			"name":        tmpl.Name,
			"description": tmpl.Description,
			"workspaces":  count,
		})
	}

	c.JSON(http.StatusOK, templates)
}

// Import handles POST /org/import — creates an entire org from a template.
func (h *OrgHandler) Import(c *gin.Context) {
	var body struct {
		Dir      string      `json:"dir"`      // org template directory name
		Template OrgTemplate `json:"template"` // or inline template
	}
	if err := c.ShouldBindJSON(&body); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	var tmpl OrgTemplate
	var orgBaseDir string // base directory for files_dir resolution

	if body.Dir != "" {
		orgBaseDir = filepath.Join(h.orgDir, body.Dir)
		orgFile := filepath.Join(orgBaseDir, "org.yaml")
		data, err := os.ReadFile(orgFile)
		if err != nil {
			c.JSON(http.StatusNotFound, gin.H{"error": fmt.Sprintf("org template not found: %s", body.Dir)})
			return
		}
		if err := yaml.Unmarshal(data, &tmpl); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": fmt.Sprintf("invalid YAML: %v", err)})
			return
		}
	} else if body.Template.Name != "" {
		tmpl = body.Template
	} else {
		c.JSON(http.StatusBadRequest, gin.H{"error": "provide 'dir' or 'template'"})
		return
	}

	results := []map[string]interface{}{}
	var createErr error

	// Recursively create workspaces
	for _, ws := range tmpl.Workspaces {
		if err := h.createWorkspaceTree(ws, nil, tmpl.Defaults, orgBaseDir, &results); err != nil {
			createErr = err
			break
		}
	}

	status := http.StatusCreated
	resp := gin.H{
		"org":        tmpl.Name,
		"workspaces": results,
		"count":      len(results),
	}
	if createErr != nil {
		status = http.StatusMultiStatus
		resp["error"] = createErr.Error()
	}

	log.Printf("Org import: %s — %d workspaces created", tmpl.Name, len(results))
	c.JSON(status, resp)
}

// createWorkspaceTree recursively creates a workspace and its children.
func (h *OrgHandler) createWorkspaceTree(ws OrgWorkspace, parentID *string, defaults OrgDefaults, orgBaseDir string, results *[]map[string]interface{}) error {
	// Apply defaults
	runtime := ws.Runtime
	if runtime == "" {
		runtime = defaults.Runtime
	}
	if runtime == "" {
		runtime = "langgraph"
	}
	tier := ws.Tier
	if tier == 0 {
		tier = defaults.Tier
	}
	if tier == 0 {
		tier = 2
	}

	id := uuid.New().String()
	awarenessNS := workspaceAwarenessNamespace(id)

	var role interface{}
	if ws.Role != "" {
		role = ws.Role
	}

	// Validate and convert workspace_dir to NULL if empty
	var workspaceDir interface{}
	if ws.WorkspaceDir != "" {
		if err := validateWorkspaceDir(ws.WorkspaceDir); err != nil {
			return fmt.Errorf("workspace %s: %w", ws.Name, err)
		}
		workspaceDir = ws.WorkspaceDir
	}

	// Insert workspace
	_, err := db.DB.Exec(`
		INSERT INTO workspaces (id, name, role, tier, runtime, awareness_namespace, status, parent_id, workspace_dir)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`, id, ws.Name, role, tier, runtime, awarenessNS, "provisioning", parentID, workspaceDir)
	if err != nil {
		log.Printf("Org import: failed to create %s: %v", ws.Name, err)
		return fmt.Errorf("failed to create %s: %w", ws.Name, err)
	}

	// Canvas layout with coordinates from YAML
	db.DB.Exec(`INSERT INTO canvas_layouts (workspace_id, x, y) VALUES ($1, $2, $3)`, id, ws.Canvas.X, ws.Canvas.Y)

	// Broadcast
	h.broadcaster.RecordAndBroadcast(context.Background(), "WORKSPACE_PROVISIONING", id, map[string]interface{}{
		"name": ws.Name, "tier": tier,
	})

	// Handle external workspaces
	if ws.External {
		db.DB.Exec(`UPDATE workspaces SET status = 'online', url = $1 WHERE id = $2`, ws.URL, id)
		h.broadcaster.RecordAndBroadcast(context.Background(), "WORKSPACE_ONLINE", id, map[string]interface{}{
			"name": ws.Name, "external": true,
		})
	} else if h.provisioner != nil {
		// Provision container
		payload := models.CreateWorkspacePayload{
			Name: ws.Name, Tier: tier, Runtime: runtime, Model: ws.Model,
			WorkspaceDir: ws.WorkspaceDir,
		}
		templatePath := ""
		if ws.Template != "" {
			tp := filepath.Join(h.configsDir, ws.Template)
			if _, err := os.Stat(tp); err == nil {
				templatePath = tp
			}
		}
		if templatePath == "" {
			runtimeDefault := filepath.Join(h.configsDir, runtime+"-default")
			if _, err := os.Stat(runtimeDefault); err == nil {
				templatePath = runtimeDefault
			}
		}

		// Always generate default config.yaml (runtime, model, tier, etc.)
		configFiles := h.workspace.ensureDefaultConfig(id, payload)

		// Copy files_dir contents on top (system-prompt.md, CLAUDE.md, skills/, etc.)
		// Uses templatePath for CopyTemplateToContainer — runs AFTER configFiles are written
		if ws.FilesDir != "" && orgBaseDir != "" {
			filesPath := filepath.Join(orgBaseDir, ws.FilesDir)
			if info, err := os.Stat(filesPath); err == nil && info.IsDir() {
				templatePath = filesPath
			}
		}

		// Pre-install plugins: copy from registry into configFiles as plugins/<name>/*
		plugins := ws.Plugins
		if len(plugins) == 0 {
			plugins = defaults.Plugins
		}
		if len(plugins) > 0 {
			if configFiles == nil {
				configFiles = map[string][]byte{}
			}
			pluginsBase, _ := filepath.Abs(filepath.Join(h.configsDir, "..", "plugins"))
			for _, pluginName := range plugins {
				pluginSrc := filepath.Join(pluginsBase, pluginName)
				if info, err := os.Stat(pluginSrc); err != nil || !info.IsDir() {
					log.Printf("Org import: plugin %s not found at %s, skipping", pluginName, pluginSrc)
					continue
				}
				filepath.Walk(pluginSrc, func(path string, info os.FileInfo, err error) error {
					if err != nil || info.IsDir() {
						return nil
					}
					rel, _ := filepath.Rel(pluginSrc, path)
					data, readErr := os.ReadFile(path)
					if readErr == nil {
						configFiles["plugins/"+pluginName+"/"+rel] = data
					}
					return nil
				})
			}
		}

		// Inline system_prompt (only if no files_dir provides one)
		if ws.SystemPrompt != "" {
			if configFiles == nil {
				configFiles = map[string][]byte{}
			}
			configFiles["system-prompt.md"] = []byte(ws.SystemPrompt)
		}

		// Inject secrets from .env files as workspace secrets.
		// Resolution: workspace .env → org root .env (workspace overrides org root).
		// Each line: KEY=VALUE → stored as encrypted workspace secret.
		envVars := map[string]string{}
		if orgBaseDir != "" {
			// 1. Org root .env (shared defaults)
			parseEnvFile(filepath.Join(orgBaseDir, ".env"), envVars)
			// 2. Workspace-specific .env (overrides)
			if ws.FilesDir != "" {
				parseEnvFile(filepath.Join(orgBaseDir, ws.FilesDir, ".env"), envVars)
			}
		}
		// Store as workspace secrets via DB (encrypted if key is set, raw otherwise)
		for key, value := range envVars {
			var encrypted []byte
			if crypto.IsEnabled() {
				var err error
				encrypted, err = crypto.Encrypt([]byte(value))
				if err != nil {
					log.Printf("Org import: failed to encrypt secret %s for %s: %v", key, ws.Name, err)
					continue
				}
			} else {
				encrypted = []byte(value) // store raw when encryption disabled
			}
			db.DB.Exec(`
				INSERT INTO workspace_secrets (workspace_id, key, encrypted_value)
				VALUES ($1, $2, $3)
				ON CONFLICT (workspace_id, key) DO UPDATE SET encrypted_value = $3, updated_at = now()
			`, id, key, encrypted)
		}

		go h.workspace.provisionWorkspace(id, templatePath, configFiles, payload)
	}

	*results = append(*results, map[string]interface{}{
		"id":   id,
		"name": ws.Name,
		"tier":  tier,
	})

	// Recurse into children
	for _, child := range ws.Children {
		if err := h.createWorkspaceTree(child, &id, defaults, orgBaseDir, results); err != nil {
			return err
		}
		time.Sleep(500 * time.Millisecond) // stagger to avoid Docker throttling
	}

	return nil
}

func countWorkspaces(workspaces []OrgWorkspace) int {
	count := len(workspaces)
	for _, ws := range workspaces {
		count += countWorkspaces(ws.Children)
	}
	return count
}

// parseEnvFile reads a .env file and adds KEY=VALUE pairs to the map.
// Skips comments (#) and empty lines. Values can be quoted.
func parseEnvFile(path string, out map[string]string) {
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		value := strings.TrimSpace(parts[1])
		// Strip surrounding quotes
		if len(value) >= 2 && ((value[0] == '"' && value[len(value)-1] == '"') || (value[0] == '\'' && value[len(value)-1] == '\'')) {
			value = value[1 : len(value)-1]
		}
		if key != "" && value != "" {
			out[key] = value
		}
	}
}

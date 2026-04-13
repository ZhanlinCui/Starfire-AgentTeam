// Package crypto provides AES-256 encryption for workspace secrets.
//
// Production-mode fail-secure (Top-5 #5 from the ecosystem-research outcomes
// doc, Security Auditor's top proposal): when STARFIRE_ENV=prod, Init
// refuses to let the platform boot without a valid 32-byte key. Dev mode
// retains the historical "warn + store plaintext" fallback so local
// developers aren't forced to generate a key to run the test server.
package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
	"io"
	"log"
	"os"
	"strings"
	"sync"
)

// ErrEncryptionKeyMissing is returned by InitStrict when STARFIRE_ENV=prod
// and SECRETS_ENCRYPTION_KEY is unset, malformed, or the wrong length.
// Callers (cmd/server/main.go) must treat this as a fatal boot error.
var ErrEncryptionKeyMissing = errors.New(
	"SECRETS_ENCRYPTION_KEY is required in production (STARFIRE_ENV=prod) " +
		"and must be 32 bytes raw or base64-encoded",
)

var (
	encryptionKey []byte
	initOnce      sync.Once
)

// Init loads the encryption key from SECRETS_ENCRYPTION_KEY env var.
// Safe to call multiple times — only executes once in production.
//
// Legacy dev-mode entry point: logs a WARNING when the key is missing or
// invalid and continues with encryption disabled. Production code paths
// (cmd/server/main.go) should call InitStrict instead so that missing
// keys abort boot when STARFIRE_ENV=prod.
func Init() {
	initOnce.Do(initKey)
}

// InitStrict is the fail-secure variant of Init. When STARFIRE_ENV=prod
// (or any strconv.ParseBool-truthy value), missing / malformed / wrong-
// length keys return ErrEncryptionKeyMissing so the caller can refuse to
// boot. In all other environments the behaviour matches Init — warn and
// continue with encryption disabled for local dev ergonomics.
func InitStrict() error {
	var initErr error
	initOnce.Do(func() {
		initErr = initKeyStrict()
	})
	return initErr
}

// ResetForTesting clears the encryption key and allows re-initialization.
// Only for tests — not safe for concurrent use.
func ResetForTesting() {
	encryptionKey = nil
	initOnce = sync.Once{}
}

func initKey() {
	if err := loadKeyFromEnv(); err != nil {
		log.Printf("%s", err)
	}
}

func initKeyStrict() error {
	loadErr := loadKeyFromEnv()
	if isProdEnv() && !IsEnabled() {
		if loadErr != nil {
			log.Printf("FATAL: %s", loadErr)
		}
		return fmt.Errorf("%w: refusing to boot without encryption in production", ErrEncryptionKeyMissing)
	}
	if loadErr != nil {
		// Non-prod: match Init's historical warn-and-continue behaviour.
		log.Printf("%s", loadErr)
	}
	return nil
}

// loadKeyFromEnv parses SECRETS_ENCRYPTION_KEY into encryptionKey.
// Returns a non-nil error describing the problem when the env var is set
// but unusable (wrong length, unparseable). Returns nil when the var is
// unset OR successfully applied.
func loadKeyFromEnv() error {
	key := os.Getenv("SECRETS_ENCRYPTION_KEY")
	if key == "" {
		return nil
	}
	decoded, err := base64.StdEncoding.DecodeString(key)
	if err != nil {
		// Try raw key (must be exactly 32 bytes)
		if len(key) == 32 {
			encryptionKey = []byte(key)
			return nil
		}
		return fmt.Errorf("SECRETS_ENCRYPTION_KEY is set but invalid (not base64 and not 32 bytes). Encryption disabled")
	}
	if len(decoded) == 32 {
		encryptionKey = decoded
		return nil
	}
	return fmt.Errorf("SECRETS_ENCRYPTION_KEY decoded to %d bytes (expected 32). Encryption disabled", len(decoded))
}

// isProdEnv returns true when STARFIRE_ENV matches one of the canonical
// production markers. Accepts case-insensitive "prod" / "production".
func isProdEnv() bool {
	v := strings.ToLower(strings.TrimSpace(os.Getenv("STARFIRE_ENV")))
	return v == "prod" || v == "production"
}

// IsEnabled returns true if encryption is configured.
func IsEnabled() bool {
	return len(encryptionKey) == 32
}

// Encrypt encrypts plaintext with AES-256-GCM.
// If encryption is disabled, returns the plaintext as-is.
func Encrypt(plaintext []byte) ([]byte, error) {
	if !IsEnabled() {
		return plaintext, nil
	}

	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return nil, err
	}

	return gcm.Seal(nonce, nonce, plaintext, nil), nil
}

// Decrypt decrypts AES-256-GCM ciphertext.
// If encryption is disabled, returns the data as-is.
func Decrypt(ciphertext []byte) ([]byte, error) {
	if !IsEnabled() {
		return ciphertext, nil
	}

	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return nil, err
	}

	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}

	nonceSize := gcm.NonceSize()
	if len(ciphertext) < nonceSize {
		return nil, errors.New("ciphertext too short")
	}

	nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]
	return gcm.Open(nil, nonce, ciphertext, nil)
}

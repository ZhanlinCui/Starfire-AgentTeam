package channels

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
)

const telegramPollInterval = 2 * time.Second

// TelegramAdapter implements ChannelAdapter for Telegram Bot API.
type TelegramAdapter struct{}

func (t *TelegramAdapter) Type() string        { return "telegram" }
func (t *TelegramAdapter) DisplayName() string { return "Telegram" }

func (t *TelegramAdapter) ValidateConfig(config map[string]interface{}) error {
	if _, ok := config["bot_token"]; !ok {
		return fmt.Errorf("missing required field: bot_token")
	}
	if _, ok := config["chat_id"]; !ok {
		return fmt.Errorf("missing required field: chat_id")
	}
	return nil
}

// welcomeMessage is sent when a user sends /start to the bot (acknowledgment only).
const welcomeMessage = "✅ Bot connected and ready.\n\nYour chat ID: `%d`\n\nPaste this ID in Starfire to link this chat to an agent, or use 'Detect Chats' to auto-fill it."

// DiscoverChats calls Telegram getUpdates to find groups/chats the bot has been added to.
// It also auto-replies to any /start commands so the user knows the bot is alive.
func (t *TelegramAdapter) DiscoverChats(ctx context.Context, botToken string) ([]map[string]interface{}, error) {
	bot, err := tgbotapi.NewBotAPI(botToken)
	if err != nil {
		return nil, fmt.Errorf("invalid bot token: %w", err)
	}

	// Remove webhook so getUpdates works
	bot.Request(tgbotapi.DeleteWebhookConfig{})

	u := tgbotapi.NewUpdate(0)
	u.Timeout = 5 // Short timeout — just grab what's available
	u.Limit = 100

	updates, err := bot.GetUpdates(u)
	if err != nil {
		return nil, fmt.Errorf("failed to get updates: %w", err)
	}

	// Deduplicate by chat ID, auto-reply to /start during discovery
	seen := map[int64]bool{}
	var chats []map[string]interface{}
	for _, update := range updates {
		if update.Message == nil {
			continue
		}
		chat := update.Message.Chat

		// Auto-reply to /start so user knows the bot works
		if strings.HasPrefix(update.Message.Text, "/start") {
			reply := tgbotapi.NewMessage(chat.ID, fmt.Sprintf(welcomeMessage, chat.ID))
			reply.ParseMode = "Markdown"
			if _, sendErr := bot.Send(reply); sendErr != nil {
				// Retry without Markdown
				reply.ParseMode = ""
				bot.Send(reply)
			}
		}

		if seen[chat.ID] {
			continue
		}
		seen[chat.ID] = true

		name := chat.Title
		if name == "" {
			name = chat.FirstName
			if chat.LastName != "" {
				name += " " + chat.LastName
			}
		}

		chats = append(chats, map[string]interface{}{
			"chat_id": strconv.FormatInt(chat.ID, 10),
			"name":    name,
			"type":    chat.Type,
		})
	}

	return chats, nil
}

// parseChatIDs splits a comma-separated chat_id string into individual IDs.
func parseChatIDs(config map[string]interface{}) []string {
	raw, _ := config["chat_id"].(string)
	if raw == "" {
		return nil
	}
	var ids []string
	for _, s := range strings.Split(raw, ",") {
		s = strings.TrimSpace(s)
		if s != "" {
			ids = append(ids, s)
		}
	}
	return ids
}

// isChatAllowed checks if a chat ID is in the configured list.
func isChatAllowed(config map[string]interface{}, chatID string) bool {
	ids := parseChatIDs(config)
	if len(ids) == 0 {
		return true // no restriction
	}
	for _, id := range ids {
		if id == chatID {
			return true
		}
	}
	return false
}

func (t *TelegramAdapter) SendMessage(ctx context.Context, config map[string]interface{}, chatID string, text string) error {
	token, _ := config["bot_token"].(string)
	if token == "" {
		return fmt.Errorf("bot_token not configured")
	}

	cid, err := strconv.ParseInt(chatID, 10, 64)
	if err != nil {
		return fmt.Errorf("invalid chat_id %q: %w", chatID, err)
	}

	bot, err := tgbotapi.NewBotAPI(token)
	if err != nil {
		return fmt.Errorf("telegram bot init: %w", err)
	}

	msg := tgbotapi.NewMessage(cid, text)
	msg.ParseMode = "Markdown"
	_, err = bot.Send(msg)
	if err != nil {
		// Retry without Markdown if it fails (agent response may have bad formatting)
		msg.ParseMode = ""
		_, err = bot.Send(msg)
	}
	return err
}

func (t *TelegramAdapter) ParseWebhook(c *gin.Context, config map[string]interface{}) (*InboundMessage, error) {
	body, err := io.ReadAll(c.Request.Body)
	if err != nil {
		return nil, fmt.Errorf("read body: %w", err)
	}

	var update tgbotapi.Update
	if err := json.Unmarshal(body, &update); err != nil {
		return nil, fmt.Errorf("parse telegram update: %w", err)
	}

	if update.Message == nil {
		return nil, nil // Not a message update (e.g. callback, edit)
	}

	chatID := strconv.FormatInt(update.Message.Chat.ID, 10)
	userID := strconv.FormatInt(update.Message.From.ID, 10)

	username := update.Message.From.UserName
	if username == "" {
		username = update.Message.From.FirstName
	}

	return &InboundMessage{
		ChatID:    chatID,
		UserID:    userID,
		Username:  username,
		Text:      update.Message.Text,
		MessageID: strconv.Itoa(update.Message.MessageID),
		Metadata: map[string]string{
			"chat_type":  update.Message.Chat.Type,
			"first_name": update.Message.From.FirstName,
			"last_name":  update.Message.From.LastName,
		},
	}, nil
}

func (t *TelegramAdapter) StartPolling(ctx context.Context, config map[string]interface{}, onMessage MessageHandler) error {
	token, _ := config["bot_token"].(string)
	if token == "" {
		return fmt.Errorf("bot_token not configured")
	}

	channelID, _ := config["_channel_id"].(string) // injected by manager
	chatIDs := parseChatIDs(config)

	bot, err := tgbotapi.NewBotAPI(token)
	if err != nil {
		return fmt.Errorf("telegram bot init: %w", err)
	}

	// Remove any existing webhook so polling works
	if _, err := bot.Request(tgbotapi.DeleteWebhookConfig{}); err != nil {
		log.Printf("Channels: Telegram failed to delete webhook (polling may not work): %v", err)
	}

	u := tgbotapi.NewUpdate(0)
	u.Timeout = 30

	log.Printf("Channels: Telegram polling started for chats %v (bot: @%s)", chatIDs, bot.Self.UserName)

	for {
		select {
		case <-ctx.Done():
			log.Printf("Channels: Telegram polling stopped for chats %v", chatIDs)
			return nil
		default:
		}

		updates, err := bot.GetUpdates(u)
		if err != nil {
			log.Printf("Channels: Telegram poll error: %v", err)
			select {
			case <-ctx.Done():
				return nil
			case <-time.After(telegramPollInterval):
				continue
			}
		}

		for _, update := range updates {
			u.Offset = update.UpdateID + 1

			if update.Message == nil {
				continue
			}

			chatID := strconv.FormatInt(update.Message.Chat.ID, 10)

			// Only process messages from configured chats
			if !isChatAllowed(config, chatID) {
				continue
			}

			// Auto-reply to /start without forwarding to the agent
			if strings.HasPrefix(update.Message.Text, "/start") {
				reply := tgbotapi.NewMessage(update.Message.Chat.ID, "✅ Connected to Starfire agent. Send a message and I'll forward it.")
				bot.Send(reply)
				continue
			}

			userID := strconv.FormatInt(update.Message.From.ID, 10)
			username := update.Message.From.UserName
			if username == "" {
				username = update.Message.From.FirstName
			}

			msg := &InboundMessage{
				ChatID:    chatID,
				UserID:    userID,
				Username:  username,
				Text:      update.Message.Text,
				MessageID: strconv.Itoa(update.Message.MessageID),
				Metadata: map[string]string{
					"chat_type":  update.Message.Chat.Type,
					"first_name": update.Message.From.FirstName,
					"last_name":  update.Message.From.LastName,
				},
			}

			if err := onMessage(ctx, channelID, msg); err != nil {
				log.Printf("Channels: Telegram message handler error: %v", err)
			}
		}
	}
}

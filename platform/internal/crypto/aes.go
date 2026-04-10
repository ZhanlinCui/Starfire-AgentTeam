// Package crypto provides AES-256 encryption for workspace secrets.
package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"io"
	"log"
	"os"
	"sync"
)

var (
	encryptionKey []byte
	initOnce      sync.Once
)

// Init loads the encryption key from SECRETS_ENCRYPTION_KEY env var.
// Safe to call multiple times — only executes once in production.
func Init() {
	initOnce.Do(initKey)
}

// ResetForTesting clears the encryption key and allows re-initialization.
// Only for tests — not safe for concurrent use.
func ResetForTesting() {
	encryptionKey = nil
	initOnce = sync.Once{}
}

func initKey() {
	key := os.Getenv("SECRETS_ENCRYPTION_KEY")
	if key == "" {
		return
	}
	decoded, err := base64.StdEncoding.DecodeString(key)
	if err != nil {
		// Try raw key (must be exactly 32 bytes)
		if len(key) == 32 {
			encryptionKey = []byte(key)
		} else {
			log.Printf("WARNING: SECRETS_ENCRYPTION_KEY is set but invalid (not base64 and not 32 bytes). Encryption disabled.")
		}
		return
	}
	if len(decoded) == 32 {
		encryptionKey = decoded
	} else {
		log.Printf("WARNING: SECRETS_ENCRYPTION_KEY decoded to %d bytes (expected 32). Encryption disabled.", len(decoded))
	}
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

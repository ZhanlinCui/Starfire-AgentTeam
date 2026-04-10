package crypto

import (
	"encoding/base64"
	"os"
	"testing"
)

func resetKey() {
	ResetForTesting()
}

func TestInit_NoEnvVar(t *testing.T) {
	resetKey()
	os.Unsetenv("SECRETS_ENCRYPTION_KEY")
	Init()
	if IsEnabled() {
		t.Error("expected encryption disabled when env var not set")
	}
}

func TestInit_ValidBase64Key(t *testing.T) {
	resetKey()
	// 32-byte key encoded as base64
	key := make([]byte, 32)
	for i := range key {
		key[i] = byte(i + 1)
	}
	os.Setenv("SECRETS_ENCRYPTION_KEY", base64.StdEncoding.EncodeToString(key))
	defer os.Unsetenv("SECRETS_ENCRYPTION_KEY")

	Init()

	if !IsEnabled() {
		t.Error("expected encryption enabled with valid 32-byte base64 key")
	}
	resetKey()
}

func TestInit_Valid32ByteRawKey(t *testing.T) {
	resetKey()
	// 32-byte key that is NOT valid base64 — forces raw byte path
	rawKey := "abcdefghijklmnopqrstuvwxyz!@#$%^" // 32 chars, not valid base64
	os.Setenv("SECRETS_ENCRYPTION_KEY", rawKey)
	defer os.Unsetenv("SECRETS_ENCRYPTION_KEY")

	Init()

	if !IsEnabled() {
		t.Error("expected encryption enabled with 32-byte raw key")
	}
	resetKey()
}

func TestInit_InvalidKey_TooShort(t *testing.T) {
	resetKey()
	os.Setenv("SECRETS_ENCRYPTION_KEY", "tooshort")
	defer os.Unsetenv("SECRETS_ENCRYPTION_KEY")

	Init()

	if IsEnabled() {
		t.Error("expected encryption disabled for short invalid key")
	}
}

func TestInit_Base64Key_Wrong_Length(t *testing.T) {
	resetKey()
	// Valid base64 but decodes to 16 bytes, not 32
	key := make([]byte, 16)
	os.Setenv("SECRETS_ENCRYPTION_KEY", base64.StdEncoding.EncodeToString(key))
	defer os.Unsetenv("SECRETS_ENCRYPTION_KEY")

	Init()

	if IsEnabled() {
		t.Error("expected encryption disabled for 16-byte base64 key")
	}
}

func TestEncryptDecrypt_RoundTrip(t *testing.T) {
	resetKey()
	key := make([]byte, 32)
	for i := range key {
		key[i] = byte(i + 42)
	}
	os.Setenv("SECRETS_ENCRYPTION_KEY", base64.StdEncoding.EncodeToString(key))
	defer os.Unsetenv("SECRETS_ENCRYPTION_KEY")
	Init()
	defer resetKey()

	plaintext := []byte("super-secret-api-key-value")

	ciphertext, err := Encrypt(plaintext)
	if err != nil {
		t.Fatalf("Encrypt failed: %v", err)
	}

	if string(ciphertext) == string(plaintext) {
		t.Error("ciphertext should differ from plaintext")
	}

	decrypted, err := Decrypt(ciphertext)
	if err != nil {
		t.Fatalf("Decrypt failed: %v", err)
	}

	if string(decrypted) != string(plaintext) {
		t.Errorf("expected %q, got %q", plaintext, decrypted)
	}
}

func TestEncrypt_Disabled_ReturnsPlaintext(t *testing.T) {
	resetKey()
	// No key set → passthrough mode

	input := []byte("not encrypted")
	out, err := Encrypt(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if string(out) != string(input) {
		t.Errorf("expected passthrough, got %q", out)
	}
}

func TestDecrypt_Disabled_ReturnsInput(t *testing.T) {
	resetKey()

	input := []byte("raw value")
	out, err := Decrypt(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if string(out) != string(input) {
		t.Errorf("expected passthrough, got %q", out)
	}
}

func TestDecrypt_TooShort_ReturnsError(t *testing.T) {
	resetKey()
	key := make([]byte, 32)
	for i := range key {
		key[i] = byte(i)
	}
	os.Setenv("SECRETS_ENCRYPTION_KEY", base64.StdEncoding.EncodeToString(key))
	defer os.Unsetenv("SECRETS_ENCRYPTION_KEY")
	Init()
	defer resetKey()

	// Ciphertext shorter than nonce (12 bytes for GCM)
	_, err := Decrypt([]byte("short"))
	if err == nil {
		t.Error("expected error for ciphertext shorter than nonce size")
	}
}

func TestEncryptDecrypt_EmptyInput(t *testing.T) {
	resetKey()
	key := make([]byte, 32)
	for i := range key {
		key[i] = byte(i + 10)
	}
	os.Setenv("SECRETS_ENCRYPTION_KEY", base64.StdEncoding.EncodeToString(key))
	defer os.Unsetenv("SECRETS_ENCRYPTION_KEY")
	Init()
	defer resetKey()

	ciphertext, err := Encrypt([]byte(""))
	if err != nil {
		t.Fatalf("Encrypt empty failed: %v", err)
	}

	decrypted, err := Decrypt(ciphertext)
	if err != nil {
		t.Fatalf("Decrypt empty failed: %v", err)
	}

	if string(decrypted) != "" {
		t.Errorf("expected empty string, got %q", decrypted)
	}
}

func TestIsEnabled_FalseByDefault(t *testing.T) {
	resetKey()
	if IsEnabled() {
		t.Error("expected IsEnabled to return false when key is nil")
	}
}

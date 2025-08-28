# Makefile for Mobile-Agent shell bypass wrappers
# Optimized for ARM64 NetHunter environment

# Detect architecture
ARCH := $(shell uname -m)
TARGET_ARCH := aarch64

# Compiler selection based on architecture
ifeq ($(ARCH),aarch64)
    CC := gcc
    CFLAGS := -O2 -march=armv8-a
else ifeq ($(ARCH),arm64)
    CC := gcc  
    CFLAGS := -O2 -march=armv8-a
else
    CC := aarch64-linux-gnu-gcc
    CFLAGS := -static -O2
endif

# Default target
all: agent-noshrc

# ARM64-optimized C wrapper compilation
agent-noshrc: agent-noshrc.c
	@echo "🔧 Compiling ARM64 C wrapper..."
	@echo "   Architecture: $(ARCH)"
	@echo "   Using compiler: $(CC)"
	@if $(CC) $(CFLAGS) -o agent-noshrc agent-noshrc.c 2>/dev/null; then \
		echo "✅ ARM64-optimized compilation succeeded"; \
	elif gcc -o agent-noshrc agent-noshrc.c 2>/dev/null; then \
		echo "✅ Standard gcc compilation succeeded"; \
	elif gcc -static -o agent-noshrc agent-noshrc.c 2>/dev/null; then \
		echo "✅ Static linking compilation succeeded"; \
	elif clang -o agent-noshrc agent-noshrc.c 2>/dev/null; then \
		echo "✅ Clang compilation succeeded"; \
	elif aarch64-linux-gnu-gcc -static -o agent-noshrc agent-noshrc.c 2>/dev/null; then \
		echo "✅ ARM64 cross-compilation succeeded"; \
	else \
		echo "❌ All compilation attempts failed"; \
		exit 1; \
	fi
	@chmod +x agent-noshrc
	@echo "🔍 Testing compiled binary..."
	@if ./agent-noshrc --help >/dev/null 2>&1; then \
		echo "✅ ARM64 binary executes correctly"; \
	else \
		echo "⚠️  Binary may not be native ARM64"; \
	fi

# Clean build artifacts
clean:
	rm -f agent-noshrc

# Install development packages (for NetHunter/Termux)
install-deps:
	@echo "🔧 Installing build dependencies..."
	@if command -v apt >/dev/null 2>&1; then \
		apt update && apt install -y build-essential gcc; \
	elif command -v pkg >/dev/null 2>&1; then \
		pkg install clang; \
	else \
		echo "❌ No package manager found"; \
	fi

# Debug shell situation
debug-shells:
	@echo "🔍 Shell Investigation:"
	@echo "Current shell: $$0"
	@echo "/bin/sh:"
	@ls -l /bin/sh 2>/dev/null || echo "  not found"
	@echo "/bin/bash:"  
	@ls -l /bin/bash 2>/dev/null || echo "  not found"
	@echo "/bin/dash:"
	@ls -l /bin/dash 2>/dev/null || echo "  not found"
	@echo "busybox:"
	@which busybox 2>/dev/null || echo "  not found"
	@echo "Available compilers:"
	@for compiler in gcc clang cc aarch64-linux-gnu-gcc; do \
		if command -v $$compiler >/dev/null 2>&1; then \
			echo "  ✓ $$compiler"; \
		else \
			echo "  ✗ $$compiler"; \
		fi \
	done

.PHONY: all clean install-deps debug-shells
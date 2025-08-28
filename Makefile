# Makefile for Mobile-Agent shell bypass wrappers

# Default target
all: agent-noshrc

# C wrapper compilation with multiple fallbacks
agent-noshrc: agent-noshrc.c
	@echo "🔧 Compiling C wrapper..."
	@if gcc -o agent-noshrc agent-noshrc.c 2>/dev/null; then \
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
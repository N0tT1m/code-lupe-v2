# Rust Coding Agent

A terminal-based AI coding assistant that can execute code, manage files, and interact with development tools - similar to Claude Code but with your own LLM backend.

## 🎯 Project Goals

- **Terminal-Native**: Rich TUI interface for seamless development workflow
- **Secure Execution**: Sandboxed code execution using Docker containers
- **LLM Agnostic**: Plugin architecture for different coding models
- **Multi-Language**: Support for various programming languages and tools
- **File System Integration**: Direct file manipulation and project management

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   TUI Layer     │    │  Agent Core     │    │  LLM Client     │
│  (ratatui)      │◄──►│  (orchestration)│◄──►│  (your model)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       
         ▼                       ▼                       
┌─────────────────┐    ┌─────────────────┐              
│  Input Handler  │    │   Tool System   │              
│  (crossterm)    │    │  (file, shell,  │              
└─────────────────┘    │   docker, etc.) │              
                       └─────────────────┘              
                                │                        
                                ▼                        
                    ┌─────────────────┐                  
                    │  Sandbox Mgr    │                  
                    │   (bollard)     │                  
                    └─────────────────┘                  
```

## 📁 Project Structure

```
rust-coding-agent/
├── Cargo.toml                  # Dependencies and metadata
├── README.md                   # This file
├── src/
│   ├── main.rs                 # Entry point and CLI setup
│   ├── lib.rs                  # Library exports
│   ├── tui/                    # Terminal User Interface
│   │   ├── mod.rs
│   │   ├── app.rs              # Main TUI application state
│   │   ├── components/         # Reusable UI components
│   │   │   ├── mod.rs
│   │   │   ├── chat.rs         # Chat interface component
│   │   │   ├── file_tree.rs    # File browser component
│   │   │   ├── code_viewer.rs  # Code display component
│   │   │   └── status_bar.rs   # Status and progress display
│   │   ├── events.rs           # Event handling system
│   │   └── layout.rs           # Screen layout management
│   ├── agent/                  # Core agent logic
│   │   ├── mod.rs
│   │   ├── core.rs             # Main agent orchestration
│   │   ├── conversation.rs     # Conversation state management
│   │   ├── planner.rs          # Task planning and execution
│   │   └── context.rs          # Context management
│   ├── llm/                    # LLM integration layer
│   │   ├── mod.rs
│   │   ├── client.rs           # HTTP client for LLM API
│   │   ├── types.rs            # Request/response types
│   │   ├── streaming.rs        # Streaming response handling
│   │   └── providers/          # Different LLM providers
│   │       ├── mod.rs
│   │       ├── openai.rs       # OpenAI-compatible API
│   │       ├── anthropic.rs    # Anthropic Claude API
│   │       └── custom.rs       # Your custom model integration
│   ├── tools/                  # Tool system
│   │   ├── mod.rs
│   │   ├── registry.rs         # Tool registration and dispatch
│   │   ├── file_ops.rs         # File system operations
│   │   ├── shell.rs            # Shell command execution
│   │   ├── git.rs              # Git operations
│   │   ├── code_exec.rs        # Code compilation/execution
│   │   └── package_mgr.rs      # Package manager integration
│   ├── sandbox/                # Sandboxed execution
│   │   ├── mod.rs
│   │   ├── docker.rs           # Docker container management
│   │   ├── filesystem.rs       # Sandboxed file operations
│   │   └── security.rs         # Security policies
│   ├── config/                 # Configuration management
│   │   ├── mod.rs
│   │   ├── settings.rs         # Application settings
│   │   └── keybinds.rs         # Keyboard shortcuts
│   └── utils/                  # Utilities
│       ├── mod.rs
│       ├── logging.rs          # Logging setup
│       └── error.rs            # Error types and handling
├── configs/                    # Configuration files
│   ├── default.toml            # Default configuration
│   └── keybinds.toml          # Default keybindings
├── docker/                     # Docker configurations
│   ├── Dockerfile.sandbox      # Sandbox container
│   └── images/                 # Language-specific images
│       ├── python.Dockerfile
│       ├── node.Dockerfile
│       └── rust.Dockerfile
└── docs/                       # Documentation
    ├── ARCHITECTURE.md         # Detailed architecture
    ├── CONFIGURATION.md        # Configuration guide
    └── TOOLS.md               # Tool system documentation
```

## 🚀 Getting Started

### Prerequisites

- Rust (latest stable)
- Docker (for sandboxed execution)
- Your LLM API endpoint and credentials

### Initial Setup Steps

1. **Initialize Cargo Project**
   ```bash
   cargo new rust-coding-agent --bin
   cd rust-coding-agent
   ```

2. **Add Core Dependencies to Cargo.toml**
   ```toml
   [dependencies]
   # TUI and Terminal
   ratatui = "0.26"
   crossterm = "0.27"
   
   # Async Runtime
   tokio = { version = "1.0", features = ["full"] }
   
   # HTTP Client for LLM
   reqwest = { version = "0.11", features = ["json", "stream"] }
   
   # Docker Integration
   bollard = "0.16"
   
   # Serialization
   serde = { version = "1.0", features = ["derive"] }
   serde_json = "1.0"
   
   # Configuration
   config = "0.14"
   toml = "0.8"
   
   # CLI
   clap = { version = "4.0", features = ["derive"] }
   
   # Error Handling
   anyhow = "1.0"
   thiserror = "1.0"
   
   # Logging
   tracing = "0.1"
   tracing-subscriber = "0.3"
   
   # File Operations
   walkdir = "2.0"
   notify = "6.0"
   
   # Utilities
   uuid = { version = "1.0", features = ["v4"] }
   futures = "0.3"
   ```

3. **Set Up Basic Project Structure**
   - Create all the directories listed in the project structure
   - Add `mod.rs` files to make modules discoverable
   - Set up basic error types and configuration loading

### Development Phases

#### Phase 1: Foundation (Week 1-2)
- [ ] Basic TUI setup with ratatui
- [ ] Configuration system (TOML-based)
- [ ] Logging infrastructure
- [ ] Basic error handling
- [ ] CLI argument parsing

#### Phase 2: LLM Integration (Week 2-3)
- [ ] HTTP client for your LLM API
- [ ] Request/response serialization
- [ ] Streaming response handling
- [ ] Basic conversation management
- [ ] Function calling support

#### Phase 3: Tool System (Week 3-4)
- [ ] Tool registry and dispatch system
- [ ] File system operations (read, write, create, delete)
- [ ] Basic shell command execution
- [ ] Git integration (status, diff, commit)
- [ ] Simple code execution (without sandboxing first)

#### Phase 4: Sandboxing (Week 4-5)
- [ ] Docker container management
- [ ] Secure file system mounting
- [ ] Process isolation and timeouts
- [ ] Resource limits and monitoring
- [ ] Multi-language runtime support

#### Phase 5: Advanced TUI (Week 5-6)
- [ ] Split-pane layout (chat, files, code viewer)
- [ ] File tree browser with navigation
- [ ] Syntax-highlighted code viewer
- [ ] Real-time streaming output
- [ ] Keyboard shortcuts and commands

#### Phase 6: Polish (Week 6+)
- [ ] Configuration hot-reloading
- [ ] Plugin system for custom tools
- [ ] Session persistence
- [ ] Performance optimization
- [ ] Comprehensive error handling

## 🔧 Key Implementation Notes

### TUI Architecture
- Use `ratatui` for the interface with a component-based approach
- Implement event-driven architecture with `crossterm` for input handling
- Consider using `tui-textarea` for multi-line text input areas

### Sandboxing Strategy
- Create lightweight Docker images for each supported language
- Mount project directory as read-only, with separate writable workspace
- Implement proper cleanup and resource limits
- Consider using `podman` as Docker alternative for rootless execution

### LLM Integration
- Design provider-agnostic interface for easy model swapping
- Implement proper retry logic and error handling
- Support both streaming and non-streaming responses
- Handle function calling and tool use properly

### Tool System Design
- Each tool should be async and return structured results
- Implement proper input validation and sanitization
- Consider tool composition (chaining multiple tools)
- Add tool discovery and help system

## 🔐 Security Considerations

- Never execute untrusted code directly on host system
- Validate all file paths to prevent directory traversal
- Implement proper input sanitization for shell commands
- Use principle of least privilege for container execution
- Consider implementing approval prompts for destructive operations

## 📚 Learning Resources

- [Ratatui Book](https://ratatui.rs/) - Comprehensive TUI guide
- [Bollard Documentation](https://docs.rs/bollard/) - Docker API client
- [Tokio Tutorial](https://tokio.rs/tokio/tutorial) - Async Rust patterns
- [Clap Documentation](https://docs.rs/clap/) - CLI argument parsing

## 🤝 Next Steps

1. Start with Phase 1 and get a basic TUI running
2. Implement a simple echo-based LLM client for testing
3. Add file operations as your first tool
4. Gradually build up the sandboxing capabilities
5. Iterate on the TUI based on actual usage patterns

Remember: Start simple and iterate. Get something working end-to-end before adding complexity!

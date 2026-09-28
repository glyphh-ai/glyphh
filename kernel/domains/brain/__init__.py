"""
Ada's brain — cognitive infrastructure that loads at startup and grows over time.

The brain owns:
- Model registry (models are deployed by users, none ship installed)
- An internal LLM (Claude Haiku) Ada calls when she needs language help
- The dream loop that mines patterns and mints new capabilities
- The think pipeline that processes every request
"""

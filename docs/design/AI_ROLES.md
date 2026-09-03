# AI Role Architecture

Status: foundational direction

Fireworks does not fundamentally require two different AI models. It requires separated roles.

## Director role
The Director operates inside the running game. It interprets player intent, requests permitted world information, proposes validated game operations, directs allowed procedural material, plays NPCs, and narrates results. Its permissions are deliberately narrow.

## Creator/Developer role
The Creator/Developer role is privileged and exists for Artifactdog to inspect, design, stage, test, and develop Fireworks. Over time this role may be exposed inside Fireworks itself as Creator Mode.

Creator Mode must not become a hidden proprietary development environment. The repository remains ordinary Git-controlled source code and project-owned documentation, so a human or another compatible developer AI can repair or continue the project even if Creator Mode is broken.

## Isolation requirement
The two roles may use the same underlying model, but must not share authority merely because they share a model. They require separate:
- context construction;
- tool sets;
- permissions;
- system/project contracts;
- audit trails.

Untrusted player content must never be able to invoke Creator/Developer capabilities.

## Interchangeability
Neither role may depend on one model/provider. Fireworks-owned contracts define role behavior; adapters translate provider-specific interfaces into those contracts.

# secure-wallet
e-wallet with multi layered security

## Quickstart (Docker Compose)

1. Build and start services:

```bash
docker-compose up --build
```

2. Open the UI at: http://localhost:8501

3. Seed sample data (optional, in another terminal):

```bash
docker-compose exec app python scripts/seed.py
```

## Development (DevContainer)

Open the repository in VS Code and reopen in container (uses the provided `.devcontainer/devcontainer.json`). The container will expose ports `8501` and `27017`.

## Notes

- Default MongoDB URI inside compose: `mongodb://mongo:27017/secure_wallet`.
- Credentials and secrets should be provided via environment variables or `.env` in development.


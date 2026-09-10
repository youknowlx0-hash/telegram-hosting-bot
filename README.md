# Telegram Hosting Bot

Railway/GitHub-ready Telegram bot foundation.

Features:
- Force join + verification
- User registration
- Project upload/storage
- Project list
- Account page
- Admin panel
- User/project statistics
- Broadcast
- SQLite database
- Docker/Railway deployment

## Railway variables

BOT_TOKEN
ADMIN_ID
FORCE_CHANNELS
MAX_FILE_MB

Never commit real tokens to GitHub.

## Deploy

1. Push this repository to GitHub.
2. Railway -> New Project -> Deploy from GitHub Repo.
3. Select this repository.
4. Add the variables above.
5. Deploy.

## Important architecture note

This version stores uploaded projects but does NOT execute arbitrary uploaded code inside the bot process. The next module should use isolated deployment services/containers with resource limits and without exposing bot/database secrets to uploaded projects.

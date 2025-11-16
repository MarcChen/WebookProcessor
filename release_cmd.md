# Release commands
```bash
# Generate changelog, bump version, and create a tag
git cliff --unreleased --bump --prepend CHANGELOG.md && \
git add CHANGELOG.md && \
git commit -m "chore: release $(git cliff --bumped-version)" && \
git tag $(git cliff --bumped-version) && \
git push && \
git push --tags
```

# Update requirements command
```bash
uv export --format requirements-txt > requirements.txt
```

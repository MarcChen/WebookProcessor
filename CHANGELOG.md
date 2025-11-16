# Changelog
All notable changes to this project will be documented in this file.

w## [0.2.0] - 2025-11-16

### Bug Fixes

- Remove unused DummyWebhookEvent import ([`022257b`](https://github.com/MarcChen/Hook2SMS/commit/022257bcb7c274bce5a8bea6ed32053748aef419))
- Add missing created_at field alias in CalWebhookEvent model ([`4b932f7`](https://github.com/MarcChen/Hook2SMS/commit/4b932f73b8129b39a827dddd3978ac7d77dfda5a))

### Features

- Enhance webhook event handling with CalTriggerEvent enum ([`5169e27`](https://github.com/MarcChen/Hook2SMS/commit/5169e27592840bf8d1996229b6d3014286d70479))
- Add logging for webhook processing and healthcheck endpoint ([`9ae664e`](https://github.com/MarcChen/Hook2SMS/commit/9ae664ef6a878caa3b8cda9442e23f646cc19d60))
- Add SMS prefix to message before sending ([`2258dbf`](https://github.com/MarcChen/Hook2SMS/commit/2258dbf7b596a74c6787a78942b5ff9533f06d7a))
- Add Strava webhook processing and client integration with environment configuration ([`fa82a68`](https://github.com/MarcChen/Hook2SMS/commit/fa82a6832153e6cfecd3e30bc36dd2a7e6b2c9e2))

### Refactor

- Simplify webhook event handling ([`933ef51`](https://github.com/MarcChen/Hook2SMS/commit/933ef512d6bb2663b872615bec6536c3a51b6204))
- Enhance output_message formatting in CalWebhookEvent ([`76b3d60`](https://github.com/MarcChen/Hook2SMS/commit/76b3d60bb3622c5f321816b21998b7c35d672b07))

# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2025-09-16
- Merged PR #1 by @MarcChen: first version

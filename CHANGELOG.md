# Changelog
All notable changes to this project will be documented in this file.

w## [0.3.0] - 2025-11-20

### Bug Fixes

- Add model_config to WebhookProcessor for arbitrary types support ([`8cb169c`](https://github.com/MarcChen/WebhookProcessor/commit/8cb169cf5c0d5e8290b3572fe134523c25549328))
- Update release command to use correct version bumping for changelog and tag ([`68b9d73`](https://github.com/MarcChen/WebhookProcessor/commit/68b9d73a65e73a5bba875d45f58913e6cfeb5dc8))

### Features

- Implement webhook verification handling for Strava and enhance processing workflow ([`5ef254d`](https://github.com/MarcChen/WebhookProcessor/commit/5ef254d3b051f37643157a27a7c9f58eb59f64bf))
- Add PING event to CalTriggerEvent enumeration ([`bbdf22e`](https://github.com/MarcChen/WebhookProcessor/commit/bbdf22e61b0fa1f8c85dd9f40b0eb1a62df0d1a7))
- Implement cooldown check for GitHub action triggers ([`159dc10`](https://github.com/MarcChen/WebhookProcessor/commit/159dc10cfb9a50a8ae2d471b01fbc84d3789a778))

### Refactor

- Rename project from Hook2SMS to WebhookProcessor ([`12f833f`](https://github.com/MarcChen/WebhookProcessor/commit/12f833f8876f922a9ec403164e2f713bfd2a37ea))
- Update import statements and enhance GitHubSettings initialization ([`888c83e`](https://github.com/MarcChen/WebhookProcessor/commit/888c83e909af1caa41231c4fa1de834f3c68d1d8))
- Remove register_processor decorator and create registry for webhook processors ([`e52bc8b`](https://github.com/MarcChen/WebhookProcessor/commit/e52bc8b5666daf3d61c52f939f17b9f0d39e3ecc))


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

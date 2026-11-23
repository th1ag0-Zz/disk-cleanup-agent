# Docker, SDKs and emulators

Read when the scan shows Docker data, Android SDK/emulator images, or Xcode simulators and device support among the large items.

## Docker

Inspect `docker system df`, then list specific unused images and build caches. Propose only those, each as its own candidate.

Docker VM disk files (including the `.vhdx` files of Docker Desktop and WSL distributions) stay in place: deleting them destroys every container, image and volume. Broad `system prune` and volume removal are out of scope for cache cleanup, because volumes can contain databases.

## Android and iOS

Use the supported management tools (`sdkmanager`, `avdmanager`, `xcrun simctl`, Xcode settings). List individual obsolete SDK versions, system images, simulators and devices as separate candidates before proposing removal.

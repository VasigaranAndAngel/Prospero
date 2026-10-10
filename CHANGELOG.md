# CHANGELOG

<!-- version list -->

## v0.1.0-alpha.5 (2026-10-10)

### Bug Fixes

- Focus bar moves to wrong places
  ([`c756959`](https://github.com/VasigaranAndAngel/Prospero/commit/c7569590e08eb225f5667deed58b345bbee15061))

- Restore isinstance narrowing in the update result widget
  ([`ac7d3fc`](https://github.com/VasigaranAndAngel/Prospero/commit/ac7d3fc63b928c31c1eaa9d8d183153a96a37991))

### Features

- Allowlisted package manager with hash pinned wheels
  ([`f5915e5`](https://github.com/VasigaranAndAngel/Prospero/commit/f5915e525acef5e1ff6da86c9a4e60df11367723))

- An attempt to load recent files associated to it's app.
  ([`98b6909`](https://github.com/VasigaranAndAngel/Prospero/commit/98b6909d9ab6779d2c54a39073d0fdfc38c35b9d))

- Focus bar
  ([`e4a4326`](https://github.com/VasigaranAndAngel/Prospero/commit/e4a4326e8506fdab0eed569356d5f6e56b7b196b))

- Global color calculator base implementation.
  ([`a5ba756`](https://github.com/VasigaranAndAngel/Prospero/commit/a5ba756dfea60a0aea53d0da8c4bbc2e2d943f49))

- New placeholder token: app.result_count
  ([`f8da8f8`](https://github.com/VasigaranAndAngel/Prospero/commit/f8da8f820c4a0cfed16f0f03fc7e91cef14a8a0b))

- Removes duplicate .lnk files from app list.
  ([`466834f`](https://github.com/VasigaranAndAngel/Prospero/commit/466834f8ef544649812ad4ffcc07a2e935f4939d))

- Show simple suggestion in query box.
  ([`8196720`](https://github.com/VasigaranAndAngel/Prospero/commit/81967203303fb459457d6540deda40dffaeaad97))

- WCAG and few more color calculation implementation in color_calculator
  ([`ec7a74b`](https://github.com/VasigaranAndAngel/Prospero/commit/ec7a74b9854c9018b8f06648c75582aca02bb13b))

### Refactoring

- Change config file path to ~/.config/Prospero/Prospero.toml
  ([`b1ab8be`](https://github.com/VasigaranAndAngel/Prospero/commit/b1ab8be76a8df3e40ad187b4d20a46dd76b71653))

- Network handling is generalized.
  ([`d11345b`](https://github.com/VasigaranAndAngel/Prospero/commit/d11345bbd077a8c1bcc495439fcb5aa31fe0cc44))

- Query box placeholder formatter and placeholder tokens
  ([`f280cb7`](https://github.com/VasigaranAndAngel/Prospero/commit/f280cb772bf4d271fc87437c1a3eab7a741bd67d))


## v0.1.0-alpha.4 (2026-09-23)

### Features

- Customizable system info rendering in query box.
  ([`a82f650`](https://github.com/VasigaranAndAngel/Prospero/commit/a82f65081ded3d71b13fdd2cebbe74861327c2c6))

- Placeholder formatter implementation.
  ([`a82f650`](https://github.com/VasigaranAndAngel/Prospero/commit/a82f65081ded3d71b13fdd2cebbe74861327c2c6))

- Application can run in offline mode by passing --offline cli arg.
  ([`7b50242`](https://github.com/VasigaranAndAngel/Prospero/commit/7b502427ad9736e25fc12da819763ab2ffebd5b9))

### Refactoring

- Few refactorings here and there.
  ([`dcb1685`](https://github.com/VasigaranAndAngel/Prospero/commit/dcb1685eced74ff04499316da8307df98f2c861a))

- Argparse implementation
  ([`7b50242`](https://github.com/VasigaranAndAngel/Prospero/commit/7b502427ad9736e25fc12da819763ab2ffebd5b9))

- Provider can be enabled or disabled and few improves.
  ([`0a54f76`](https://github.com/VasigaranAndAngel/Prospero/commit/0a54f76a15d3c8bb7bc033f47e2745a0c77d850d))

- Result and Choice in providers are combined. and few improvements.
  ([`b1ba0d7`](https://github.com/VasigaranAndAngel/Prospero/commit/b1ba0d7f36f829fa0444bbb40046531614692c2a))


## v0.1.0-alpha.3 (2026-09-16)

### Bug Fixes

- Updater updates the into wrong dir.
  ([`894ca71`](https://github.com/VasigaranAndAngel/Prospero/commit/894ca713beda27f7fb9e38fdacd682c5245e29e4))


## v0.1.0-alpha.2 (2026-09-16)

### Bug Fixes

- QNetwork fails when checking for updates.
  ([`eee7b8f`](https://github.com/VasigaranAndAngel/Prospero/commit/eee7b8ff4feafc026d0b1296e61ec9a81ebaee61))


## v0.1.0-alpha.1 (2026-09-15)

### Bug Fixes

- Possible memory leak in custom vbox layout.
  ([`7a72a76`](https://github.com/VasigaranAndAngel/Prospero/commit/7a72a767d5c3547d9611bf0dc70f46e09bc99438))

- ResultBoxContainer not adjusting its size when a child widget shrinks.
  ([`60c1207`](https://github.com/VasigaranAndAngel/Prospero/commit/60c120732276c840ca1ee43384dfcdc453c37ca1))

- Same file named files are replaced by the last one when getting app details
  ([`fca5b51`](https://github.com/VasigaranAndAngel/Prospero/commit/fca5b51efb045881b16e0550f7a8082dac6d8105))

### Code Style

- Remove unwanted lines
  ([`d112205`](https://github.com/VasigaranAndAngel/Prospero/commit/d112205176e8d2bad1bb87e43db809761670f77c))

### Features

- Results scroll area is automatically scrolled to show shadow focused result widget.
  ([`0569fc9`](https://github.com/VasigaranAndAngel/Prospero/commit/0569fc9d9c68324eee1ffe5bf9370803855b491d))

### Performance Improvements

- An AnimatedVBoxLayout is implemented. now moment of result widgets are smoother and more stable.
  ([`9ec91fe`](https://github.com/VasigaranAndAngel/Prospero/commit/9ec91fe4599321b155a584c89ccd46e8d5f673e0))

- Shutdown command executes better than before
  ([`4d629d5`](https://github.com/VasigaranAndAngel/Prospero/commit/4d629d5352d5fe724fc19326ba5205e60cc0a98a))

### Refactoring

- Few changes to result widgets container and scroll area
  ([`9ec91fe`](https://github.com/VasigaranAndAngel/Prospero/commit/9ec91fe4599321b155a584c89ccd46e8d5f673e0))

- Moved CornerMaskOverlay to it's own .py file
  ([`a05a895`](https://github.com/VasigaranAndAngel/Prospero/commit/a05a8959d99f27c4bf5c8d8f94105b94aae2211a))

- Updates result of preserved result box widgets
  ([`f810244`](https://github.com/VasigaranAndAngel/Prospero/commit/f810244a1ccf286941b169d0dcd5fc2a7afe6aad))


## v0.0.2 (2026-09-10)

### Bug Fixes

- Asking for elevation on quit and chores.
  ([`d691850`](https://github.com/VasigaranAndAngel/Prospero/commit/d691850b21e7de427e41c1b374266887641c72d9))

- Import error
  ([`9cebad2`](https://github.com/VasigaranAndAngel/Prospero/commit/9cebad25b71e69c7656578a6fbfcca963bc109e7))

- Running task scheduler commands creates terminal.
  ([`8a43d2b`](https://github.com/VasigaranAndAngel/Prospero/commit/8a43d2ba7664f7e9fbb34909ba7f370cf85f4703))

- System tray icon
  ([`18806d8`](https://github.com/VasigaranAndAngel/Prospero/commit/18806d830d6b8e72f0c0c1b6cd75c29a5f12b160))

- Task scheduler handler subprocess.run uses wrong parameters
  ([`3c4e707`](https://github.com/VasigaranAndAngel/Prospero/commit/3c4e707f211d7a7e6eef5f8fd96f646faa12d0e6))


## v0.0.1 (2026-09-04)

- Initial Release

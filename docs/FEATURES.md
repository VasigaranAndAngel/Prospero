# Prospero — Feature Reference

This is the full list of everything Prospero does, everything it is working on, and everything that is planned.

Every feature follows the same shape:

1. A heading with its **status** (for example `Feature name _implemented_`).
2. A one-line summary.
3. A fold-out **How to use** section with examples.
4. A nested fold-out **Developer notes** section, for people working on the code.

**Status legend**

| Tag            | Meaning                                                          |
| -------------- | ---------------------------------------------------------------- |
| _implemented_  | Works today and is part of the main branch.                      |
| _in progress_  | Partly built, or built only on a development branch.             |
| _in review_    | Built and being tested or polished before it is considered done. |
| _planned_      | Designed or wanted, but not built yet.                           |
| _canceled_     | Thought about, then decided against.                             |

**Jump to a category**

- [Using Prospero](#using-prospero)
- [Providers](#providers)
- [Calculator](#calculator)
- [Applications](#applications)
- [Commands & Power](#commands--power)
- [Appearance & Themes](#appearance--themes)
- [Configuration & Settings](#configuration--settings)
- [Window & UI](#window--ui)
- [Query Box](#query-box)
- [Icons](#icons)
- [Online, Updates & Offline](#online-updates--offline)
- [Command Line](#command-line)
- [Integrations](#integrations)
- [Planned Providers](#planned-providers)
- [Performance & Internals](#performance--internals)
- [Known Issues](#known-issues)
- [Future Ideas](#future-ideas)

---

## Using Prospero

### Global hotkey _implemented_

Press `Alt + Space` from anywhere to open Prospero or select all query.

<details>
<summary><b>How to use</b></summary>

With Prospero running in the background, press `Alt + Space`. The window appears in front of whatever you are doing and the query box is focused, so you can start typing right away. Pressing `Esc` hides it.

On Linux the hotkey works on X11 out of the box. On Wayland, whether a global shortcut can be captured (and whether the key can be swallowed) depends on the compositor; if it does not work, bind a compositor shortcut that runs `prospero`.

<details>
<summary><b>Developer notes</b></summary>

The hotkey is handled by `src/hotkey_listener.py` using `pynput`. On Windows it installs a low-level event filter that watches for the left Alt key held while Space is pressed, emits a Qt signal, and suppresses the key so Windows does not also act on it. On other platforms pynput does not support suppressing events (on X11) so the plain listener is used and the key also reaches the focused window. `src/main.py` connects that signal to show or hide the main window.
</details>
</details>

### The main window _implemented_

A frameless, always-on-top window with rounded corners that fades and slides in when opened.

<details>
<summary><b>How to use</b></summary>

The window holds the query box at the top and the list of results below it. It always stays above other windows so it never gets buried. Drag it by the background to move it, and if "remember position" is on, it reopens where you left it.

<details>
<summary><b>Developer notes</b></summary>

Implemented in `src/ui/main_window.py`. It uses a translucent background plus a corner mask overlay (`src/ui/_corner_mas_overlay.py`) for the rounded shape. Size and position are driven by `src/configs/categories/window_geometry_category.py`.
</details>
</details>

### Fuzzy search _implemented_

Typing part of a name finds it, even if the letters are not next to each other.

<details>
<summary><b>How to use</b></summary>

You do not need to type things exactly. Typing `vsc` can find "Visual Studio Code". The best match is selected automatically, and matched letters are highlighted in each result.

<details>
<summary><b>Developer notes</b></summary>

`src/fuzzy_finder.py` implements a subsequence matcher with scoring bonuses for word boundaries, camelCase, and consecutive matches, similar to the fuzzy scoring in `fzf` and VS Code. `IncrementalMatcher` keeps a shrinking candidate list, so typing one more letter only re-checks the previous survivors instead of everything.
</details>
</details>

### Result navigation _implemented_

Move through results with the keyboard and run the one you want.

<details>
<summary><b>How to use</b></summary>

- `Tab` or `Down` — next result
- `Shift + Tab` or `Up` — previous result
- `Enter` — run the selected result
- `Esc` — close the window

The list wraps around, so pressing Down on the last result goes back to the first.

<details>
<summary><b>Developer notes</b></summary>

Focus is tracked in `MainWindow` (`_shadow_focused_idx`) and drawn by `src/ui/_focused_result_bar.py`. The results scroll area auto-scrolls to keep the focused item visible.
</details>
</details>

### Running a result _implemented_

Each result knows what to do when it is chosen, and can offer more than one action.

<details>
<summary><b>How to use</b></summary>

Press `Enter` on a result to run its main action. For example, a calculator result copies the answer, and an application result launches the app. Some results also support an "expand" action for seeing more options in the future.

<details>
<summary><b>Developer notes</b></summary>

Results extend `BaseResult` in `src/providers/base_result_and_widgets.py`. The actions are `ExecutionAction.Trigger` (the main action) and `ExecutionAction.Expand` (extra options). A result can also ask the window to close after it runs, or show a suggestion in the query box.
</details>
</details>

### Terminal mode _implemented_

Run Prospero inside a terminal instead of as a window.

<details>
<summary><b>How to use</b></summary>

```sh
prospero --cli
```

Type a query, press Enter to run the first result, and press `Ctrl + C` to quit. Matched text is shown in green.

<details>
<summary><b>Developer notes</b></summary>

`main.cli()` in `src/main.py` renders results to stdout using ANSI codes and reads input with `msvcrt` on Windows and `termios`/`tty` elsewhere. It reuses the same providers as the window, so both modes stay in sync.
</details>
</details>

### Tray icon _implemented_

Prospero lives in the system tray while it is running.

<details>
<summary><b>How to use</b></summary>

Look for the Prospero icon in the notification area (Windows) or the status area (Linux). It keeps the app in the background and gives a place to interact with it without the main window being open.

<details>
<summary><b>Developer notes</b></summary>

Created in `src/main.py` alongside the `QApplication`, using the icon files in `assets/icon/`. On Linux this needs a desktop with a status-notifier host; on GNOME you may need the AppIndicator extension.
</details>
</details>

### Auto start on login _implemented_

Ask the desktop to launch Prospero when you sign in.

<details>
<summary><b>How to use</b></summary>

Type `Add Prospero to Scheduled Tasks` and press Enter. To undo it, use `Remove Prospero from Scheduled Tasks`.

<details>
<summary><b>Developer notes</b></summary>

On Windows this is handled by `src/helpers/windows_task_schedule_handler.py`, which registers a logon task. On Linux it is handled by `src/helpers/linux_autostart.py`, which writes an XDG autostart entry to `~/.config/autostart/Prospero.desktop`. `src/helpers/__init__.py` picks the right module for the platform, and the commands live in the command provider.
</details>
</details>

---

## Providers

Providers are the pieces that answer your query. Each one looks for a different kind of result, and they all search at the same time.

### Pluggable providers _implemented_

The launcher does not hard-code what it can find. Each feature is a provider that plugs into the same system.

<details>
<summary><b>How to use</b></summary>

This is automatic. When you type, every enabled provider is asked, and all of their results are merged and sorted by score.

<details>
<summary><b>Developer notes</b></summary>

`src/providers/_base_provider.py` defines `BaseProvider` with a `search()` method. The registry in `src/providers/__init__.py` keeps a list of provider classes and live instances. See `FEATURES.md` sections below for the built-in providers.
</details>
</details>

### Enable or disable a provider _implemented_

Turn a provider on or off while the app is running.

<details>
<summary><b>How to use</b></summary>

With `--debug`, type `Enable Provider:` or `Disable Provider:` and choose the provider from the results. Providers also have enable/disable hooks that run when their state changes.

<details>
<summary><b>Developer notes</b></summary>

`enable_provider()` and `disable_provider()` in `src/providers/__init__.py` move types between `PROVIDERS_I` and `DISABLED_PROVIDERS` and call the `enable_hook()` / `disable_hook()` methods.
</details>
</details>

### Threaded search _implemented_

Every provider searches on its own background thread, so a slow provider never freezes the window.

<details>
<summary><b>How to use</b></summary>

Just type. Slow providers (like loading the app list) show a loading indicator while they work, and the window stays responsive.

<details>
<summary><b>Developer notes</b></summary>

A shared `THREAD_POOL` in `src/global_threading.py` runs the work. `BaseProvider.search_async()` submits `search()` to the pool and reports back through a callback.
</details>
</details>

### Loading indicator requests _implemented_

A provider can ask the UI to show that it is still busy.

<details>
<summary><b>How to use</b></summary>

Nothing to do — you will see the loading animation in the query box while a provider is still working. It disappears once all providers have answered.

<details>
<summary><b>Developer notes</b></summary>

Providers send a `LoadingRequest` (`src/providers/_loading_request.py`). The main window keeps a list of active requests and shows the loading state until the list is empty.
</details>
</details>

### Custom result widgets _implemented_

A provider can show its results with its own widget instead of the default row.

<details>
<summary><b>How to use</b></summary>

This is automatic per provider. For example, the updater shows a custom widget with a progress display.

<details>
<summary><b>Developer notes</b></summary>

`BaseResult` has a `result_widget_factory`. When present, the window builds that widget instead of the default `ResultBox`. Widgets should be updatable so the same one can be reused when results change.
</details>
</details>

### One dataclass for results and choices _implemented_

Search results and fuzzy-matching choices are the same object, so there is less duplication.

<details>
<summary><b>How to use</b></summary>

No user-facing action; it is an internal cleanup that makes results and matching behave consistently.

<details>
<summary><b>Developer notes</b></summary>

`BaseResult` doubles as a fuzzy choice (it has `text`, `score`, and `highlighted_indexes`). Providers build results once and hand them straight to the matcher.
</details>
</details>

### Provider-defined placeholder tokens _planned_

Let a provider register its own tokens for the query box placeholder.

<details>
<summary><b>How to use</b></summary>

Planned. Once ready, a provider could add something like a last-answer token without changing the core app.

<details>
<summary><b>Developer notes</b></summary>

`src/query_placeholder_tokens.py` already has a registration API. This work is about letting external providers use it and making `updated` fire correctly.
</details>
</details>

### Passing data between providers _planned_

A shared "payload" so one provider can hand a value to another.

<details>
<summary><b>How to use</b></summary>

Planned. The idea is to type one query, then use a result from one provider as the input for another (for example, calculate with a file's details).

<details>
<summary><b>Developer notes</b></summary>

Designed in the project notes as a `Payload` type holding a file path, text, number with unit, color, app reference, window handle, process, URI, or a list of these. No implementation exists yet.
</details>
</details>

### Auto-loading provider subclasses _canceled_

The idea was for `BaseProvider` to discover all of its subclasses automatically. It was dropped because providers still need to be imported first, and the existing enable/disable system already covers the real needs.

<details>
<summary><b>Developer notes</b></summary>

Canceled. Provider classes are still listed explicitly in `src/providers/__init__.py`.
</details>

---

## Calculator

The calculator provider evaluates math, including units, and returns an answer you can copy.

### Basic arithmetic _implemented_

Add, subtract, multiply, divide, and use parentheses.

<details>
<summary><b>How to use</b></summary>

```
2 + 2
10 * 5
(3 + 4) * 2
2 ** 10        (or 2 ^ 10)
17 % 5
12 / 4
12 x 4         (x also means multiply)
```

Supported operators: `+`, `-`, `*` or `x` (multiply), `/`, `**` or `^` (power), `%` (modulo).

<details>
<summary><b>Developer notes</b></summary>

Evaluation lives under `src/providers/calculator_provider/`. Numbers are represented by a `Value` object that carries a unit and supports arithmetic with other values and plain numbers.
</details>
</details>

### Readable numbers _implemented_

Underscores inside numbers are ignored, so you can group digits.

<details>
<summary><b>How to use</b></summary>

```
1_000_000 + 5
```

The result is the same as typing `1000000 + 5`.

<details>
<summary><b>Developer notes</b></summary>

The number patterns in the calculator strip `_` characters before evaluation.
</details>
</details>

### Scientific notation _implemented_

Numbers with exponents are understood.

<details>
<summary><b>How to use</b></summary>

```
1e3 + 2e2
```

<details>
<summary><b>Developer notes</b></summary>

Handled by the calculator's number patterns. A known gap is that a unit cannot yet be attached to a scientific number — see [Known Issues](#known-issues).
</details>
</details>

### Different number bases _implemented_

Binary, octal, and hexadecimal numbers are accepted, including with decimal points.

<details>
<summary><b>How to use</b></summary>

```
0b1010    (binary)
0o17      (octal)
0x1f      (hex)
```

<details>
<summary><b>Developer notes</b></summary>

Base prefixes are parsed by the calculator. Custom bases beyond these three are still planned.
</details>
</details>

### Multiple calculations _implemented_

Run several expressions at once by separating them with a semicolon.

<details>
<summary><b>How to use</b></summary>

```
2 + 2 ; 3 * 3 ; 10 / 2
```

Each expression is evaluated, and you get all of the answers.

<details>
<summary><b>Developer notes</b></summary>

The `;` split and per-part evaluation are handled in `src/providers/calculator_provider/`. This also understands simple variable assignment.
</details>
</details>

### Unit conversion _implemented_

Convert between units of the same kind.

<details>
<summary><b>How to use</b></summary>

```
10 km to miles
24 hours to days
5 kg in lb
```

Supported kinds include length, mass, volume, data, and time. Temperature units are recognized as well.

<details>
<summary><b>Developer notes</b></summary>

Unit definitions and factors live in `src/providers/calculator_provider/nl_calc/unit_relations.py`. Conversion checks that the two units share a dimension before converting.
</details>
</details>

### Copy the answer _implemented_

Running a calculator result copies it to the clipboard.

<details>
<summary><b>How to use</b></summary>

Type an expression and press `Enter`. The answer is copied and can be pasted anywhere with `Ctrl + V`.

<details>
<summary><b>Developer notes</b></summary>

`CalcResult.execute()` copies its text. It uses `pyperclip` if available and falls back to the Qt clipboard.
</details>
</details>

### Custom number bases _planned_

Support bases beyond binary, octal, and hexadecimal, up to base 36 and possibly higher.

<details>
<summary><b>How to use</b></summary>

Planned syntax such as `36:[0-9a-z]`. Not available yet.

<details>
<summary><b>Developer notes</b></summary>

Would extend the base parsing in the calculator. Case sensitivity is an open question for bases above 36.
</details>
</details>

### Graph calculator _in review_

Draw functions as graphs.

<details>
<summary><b>How to use</b></summary>

Not ready for everyday use yet. The plan is to show one or more graphs in a pane. The current approach using `pyqtgraph` is being evaluated because it is not yet fast and intuitive.

<details>
<summary><b>Developer notes</b></summary>

`pyqtgraph` is already a dependency. The graphing widget is an experiment on a development branch; the project notes include a PyQtGraph setup reference.
</details>
</details>

### Comparing values _planned_

Ask whether one value is bigger than another and get an explanation.

<details>
<summary><b>How to use</b></summary>

Planned. For example, `1 km > 1 cm` would answer "Yes" and explain the difference.

<details>
<summary><b>Developer notes</b></summary>

Would extend the operator handling in the calculator's value system.
</details>
</details>

### Friendlier output _planned_

Make answers read more like everyday language.

<details>
<summary><b>How to use</b></summary>

Planned. For example, `24 + 3 hours to days` could show `1 day 3 hours` instead of a single decimal number.

<details>
<summary><b>Developer notes</b></summary>

Depends on the richer `Value` design that keeps calculation details, so the output formatter knows what units are involved.
</details>
</details>

### Custom functions, constants, and units _planned_

Add your own functions, constants, and units.

<details>
<summary><b>How to use</b></summary>

Planned. One idea is a custom function that runs a Python snippet in a subprocess.

<details>
<summary><b>Developer notes</b></summary>

Needs a definition format and a loader. Related to the configurable-token work.
</details>
</details>

### Last-answer token _planned_

A token that inserts the previous calculation's result.

<details>
<summary><b>How to use</b></summary>

Planned. Useful for chaining calculations in the placeholder or a later expression.

<details>
<summary><b>Developer notes</b></summary>

The calculator already registers `provider.calc.result` and `provider.calc.last_result` placeholder tokens; the remaining work is exposing the last answer as an insertable token.
</details>
</details>

### Roman numerals _planned_

Support Roman numeral input and output.

<details>
<summary><b>How to use</b></summary>

Planned, not available yet.

<details>
<summary><b>Developer notes</b></summary>

Would be added as a number annotation in the calculator.
</details>
</details>

### Value charts _planned_

Draw a small chart for functions like `min` and `max` to show the values visually.

<details>
<summary><b>How to use</b></summary>

Planned. Would only appear when the expression evaluates to those functions.

<details>
<summary><b>Developer notes</b></summary>

Depends on the graphing work and the richer value output.
</details>
</details>

### Tokenizing rewrite _planned_

Rewrite the calculator's evaluation using a proper tokenizer.

<details>
<summary><b>How to use</b></summary>

No user-facing change expected; this is about making the calculator correct and easier to extend.

<details>
<summary><b>Developer notes</b></summary>

A general expression tokenizer and parser are being developed on the `nl-expressions` branches.
</details>
</details>

---

## Applications

The application provider finds and launches programs on your computer.

### Launch applications _implemented_

Find and open applications: Start Menu shortcuts and Microsoft Store / UWP apps on Windows, and `.desktop` entries on Linux.

<details>
<summary><b>How to use</b></summary>

Start typing an app's name, pick it from the results, and press `Enter`. On Windows both classic desktop shortcuts (`.lnk` files) and packaged apps are supported. On Linux the entries are read from the XDG data directories (`~/.local/share/applications`, `/usr/share/applications`, …).

<details>
<summary><b>Developer notes</b></summary>

`src/providers/application_provider/` builds a list of `AppResult`s. On Windows desktop apps are launched with `start "" "<path>"` and UWP apps with `start shell:appsFolder\<app_id>`. On Linux `_linux.py` parses `[Desktop Entry]` sections, strips the `Exec` field codes and launches the resulting argv directly with the current `AppDetail.exec_command`. `_get_app_details._build_full_app_list()` dispatches to the right implementation.
</details>
</details>

### App icons _implemented_

Each app result shows the program's real icon.

<details>
<summary><b>How to use</b></summary>

Just look at the result. While the icon is loading, a spinner is shown, and a default icon appears if one cannot be found.

<details>
<summary><b>Developer notes</b></summary>

On Windows icons are extracted with the Windows shell API in `src/platform_specific/windows/icons.py`. On Linux `_linux.py` resolves the freedesktop `Icon=` name to a real file (theme directories, then `/usr/share/pixmaps`) and it is loaded by `src/platform_specific/linux/icons.py`. `src/platform_specific/icons.py` is the platform facade; both feed `src/shared_ui_elements/icon.py`.
</details>
</details>

### Recent files _implemented_

Show recently used files as extra results, so you can reopen them quickly.

<details>
<summary><b>How to use</b></summary>

This is off by default. Turn on `providers.app_provider.show_recent_files` in the config (or via settings when available). Recent items then appear as `App Name Recent: file`.

Currently Windows only.

<details>
<summary><b>Developer notes</b></summary>

Recent items are read from Windows Jump Lists (`src/providers/application_provider/windows/_recents.py`) and merged into the app results when the setting is enabled. The feature is gated behind `IS_WINDOWS`, so on Linux it is simply skipped.
</details>
</details>

### Search shortcuts by path _planned_

Also match on the shortcut's path, not just its name.

<details>
<summary><b>How to use</b></summary>

Planned. Would let you find an app by where it lives, optionally without the Start Menu path prefix.

<details>
<summary><b>Developer notes</b></summary>

Would add the `.lnk` path (and possibly its target path) to the fuzzy-matching text.
</details>
</details>

### Deduplicate apps _planned_

Hide duplicate entries that point to the same program.

<details>
<summary><b>How to use</b></summary>

Planned. Duplicates would be detected by comparing the shortcut's target, arguments, and start-in folder.

<details>
<summary><b>Developer notes</b></summary>

Would read those fields from the `.lnk` file during the app-details pass.
</details>
</details>

### Open a file with an app _planned_

A bridge between the application provider and the planned file-system provider.

<details>
<summary><b>How to use</b></summary>

Planned. The idea is to pick a file and then pick the app to open it with.

<details>
<summary><b>Developer notes</b></summary>

Depends on the inter-provider payload design and the file-system provider.
</details>
</details>

---

## Commands & Power

The command provider runs built-in launcher and system commands. Type the command name and press Enter.

### Quit _implemented_

Close Prospero.

<details>
<summary><b>How to use</b></summary>

Type `Quit` (or the shortcut `q`) and press Enter.

<details>
<summary><b>Developer notes</b></summary>

Registered in `src/providers/command_provider/command_provider.py`. Calls `sys.exit()`.
</details>
</details>

### Shut down _implemented_

Shut down the computer. On Windows this respects fast startup / hybrid shutdown; on Linux it uses `systemd`/`logind`.

<details>
<summary><b>How to use</b></summary>

Type `Power: Shutdown` and press Enter.

<details>
<summary><b>Developer notes</b></summary>

Uses `shutdown_respect_hybrid` in `src/providers/command_provider/_shutdown.py`. On Windows it reads the `HiberbootEnabled` registry value to decide between a hybrid and a full shutdown (an earlier version was slow; that was fixed by improving how the shutdown is issued). On Linux it runs `systemctl poweroff`, falling back to `loginctl poweroff`.
</details>
</details>

### Restart _implemented_

Restart the computer.

<details>
<summary><b>How to use</b></summary>

Type `Power: Restart` and press Enter.

<details>
<summary><b>Developer notes</b></summary>

Runs `shutdown /r /t 0` on Windows and `systemctl reboot` (or `loginctl reboot`) on Linux, via `src/providers/command_provider/_shutdown.py`.
</details>
</details>

### Hibernate _implemented_

Hibernate the computer.

<details>
<summary><b>How to use</b></summary>

Type `Power: Hibernate` and press Enter.

<details>
<summary><b>Developer notes</b></summary>

Runs `shutdown /h` on Windows and `systemctl hibernate` on Linux. On Linux the machine must have a configured swap/resume device. A planned improvement is to hide this command when hibernation is disabled in Windows.
</details>
</details>

### Sleep _implemented_

Put the computer to sleep.

<details>
<summary><b>How to use</b></summary>

Type `Power: Sleep` and press Enter.

<details>
<summary><b>Developer notes</b></summary>

Runs `rundll32 powrprof.dll,SetSuspendState` on Windows and `systemctl suspend` on Linux, via `src/providers/command_provider/_shutdown.py`.
</details>
</details>

### Lock _implemented_

Lock the current user session.

<details>
<summary><b>How to use</b></summary>

Type `Power: Lock` and press Enter.

<details>
<summary><b>Developer notes</b></summary>

Runs `rundll32 user32.dll,LockWorkStation` on Windows. On Linux it tries `loginctl lock-session`, then `xdg-screensaver lock`.
</details>
</details>

### Check for updates _implemented_

Check for and install a newer version.

<details>
<summary><b>How to use</b></summary>

Type `Updater` and use the updater result to check for and download an update.

<details>
<summary><b>Developer notes</b></summary>

The command uses a custom result widget. The download and install logic is in `src/updater.py`.
</details>
</details>

### Scheduled startup tasks _implemented_

Add or remove Prospero from startup.

<details>
<summary><b>How to use</b></summary>

Type `Add Prospero to Scheduled Tasks` or `Remove Prospero from Scheduled Tasks` and press Enter.

<details>
<summary><b>Developer notes</b></summary>

Uses `src/helpers/windows_task_schedule_handler.py` on Windows and `src/helpers/linux_autostart.py` (XDG autostart) on Linux. `src/helpers/__init__.py` selects the one for the platform.
</details>
</details>

### Version _implemented_

See the current version.

<details>
<summary><b>How to use</b></summary>

Type `Version`; the result describes the running version.

<details>
<summary><b>Developer notes</b></summary>

Reads `VERSION` from `src/constants.py`.
</details>
</details>

### Timed commands _planned_

Run a command after a delay.

<details>
<summary><b>How to use</b></summary>

Planned. For example, `Shutdown in 5 minutes`.

<details>
<summary><b>Developer notes</b></summary>

Would add a time parser to the command provider.
</details>
</details>

### Goodbye message on shutdown _planned_

Show a short message when a shutdown command runs.

<details>
<summary><b>How to use</b></summary>

Planned.

<details>
<summary><b>Developer notes</b></summary>

A small UI addition around the shutdown command.
</details>
</details>

### Logout _planned_

Log the user out.

<details>
<summary><b>How to use</b></summary>

Planned; not implemented.

<details>
<summary><b>Developer notes</b></summary>

Would be another power option in the command provider.
</details>
</details>

### Custom commands _planned_

Add your own shell commands as results.

<details>
<summary><b>How to use</b></summary>

Planned. You would define commands in the config and they would show up as results.

<details>
<summary><b>Developer notes</b></summary>

Would extend the command registry with user-provided entries.
</details>
</details>

### Window commands _planned_

Control open windows from the launcher.

<details>
<summary><b>How to use</b></summary>

Planned commands like `Raise <Window>`, `Quit <Window>`, `Minimize <Window>`, `Maximize <Window>`, and `Restart <Window>`.

<details>
<summary><b>Developer notes</b></summary>

Needs a Windows window-enumeration helper and a new command source.
</details>
</details>

---

## Appearance & Themes

### System / Dark / Light mode _implemented_

Choose how Prospero looks, or follow the system.

<details>
<summary><b>How to use</b></summary>

Set `appearance.theme_mode` to `System`, `Dark`, or `Light` in the config. `System` follows the desktop light/dark setting (on Windows and Linux) and switches automatically.

<details>
<summary><b>Developer notes</b></summary>

Defined in `src/configs/categories/appearance_category.py`. Theme changes are applied by `src/theme/_theme.py`, which reads the system preference from `QApplication.styleHints().colorScheme()` and listens to `colorSchemeChanged`.
</details>
</details>

### Custom themes _implemented_

Use your own theme files.

<details>
<summary><b>How to use</b></summary>

Set `appearance.dark_theme` and `appearance.light_theme` to your theme files, or pass `--theme`, `--dark-theme`, and `--light-theme` on the command line. Themes are TOML files describing colors, fonts, and corner radius for the main window, query bar, results area, and result rows.

<details>
<summary><b>Developer notes</b></summary>

`src/theme/_theme.py` models a theme with `BaseWidget` sections (`main_window`, `query_bar`, `results_area`, `result`), each with background color, font, and corner radius. Invalid theme files fall back to the built-in default.
</details>
</details>

### Global color calculator _planned_

One shared color system used by both the theme and the planned color provider.

<details>
<summary><b>How to use</b></summary>

Planned behind the scenes; it would let themes and color tools agree on color math.

<details>
<summary><b>Developer notes</b></summary>

A `src/color_calculator/` module exists as a starting point using the `coloraide` library.
</details>
</details>

### Animated theme change _planned_

Smoothly animate a switch between themes.

<details>
<summary><b>How to use</b></summary>

Planned. The idea is a circular reveal when the theme changes.

<details>
<summary><b>Developer notes</b></summary>

Designed in the project notes as a `ThemeMixin` that captures the old and new themes and reveals one over the other with an expanding circle.
</details>
</details>

### Font customization _planned_

Set fonts separately for the query box, results, and descriptions, all inheriting from a base font.

<details>
<summary><b>How to use</b></summary>

Planned through the settings window.

<details>
<summary><b>Developer notes</b></summary>

The theme model already has font config per region; the missing part is exposing it in the settings UI.
</details>
</details>

### Window shadow _planned_

Add a drop shadow around the window.

<details>
<summary><b>How to use</b></summary>

Planned.

<details>
<summary><b>Developer notes</b></summary>

A UI polish task in the main window.
</details>
</details>

---

## Configuration & Settings

### TOML config file _implemented_

All settings live in one readable file.

<details>
<summary><b>How to use</b></summary>

Settings are stored in `%USERPROFILE%\.config\Prospero\Prospero.toml` on Windows and `~/.config/Prospero/Prospero.toml` on Linux, and created with defaults on first run. Pass `--config <path>` to use a different file.

<details>
<summary><b>Developer notes</b></summary>

`src/configs/_configs.py` defines the `Configs` model using `pydantic` and `pydantic-settings`, with a TOML source and `tomli-w` for writing. A singleton `CONFIGS` is created at import.
</details>
</details>

### Config auto-reload _implemented_

The app notices when the config file changes.

<details>
<summary><b>How to use</b></summary>

Edit the config file and save it; Prospero picks up the change without restarting.

<details>
<summary><b>Developer notes</b></summary>

Config values are observable (`src/config_models/_config_value.py`). The settings layer subscribes to changes and broadcasts a `ChangeEvent` to the UI.
</details>
</details>

### Maximum results _implemented_

Control how many results a provider returns.

<details>
<summary><b>How to use</b></summary>

Set `general.results_box.maximum_results` (default `5`).

<details>
<summary><b>Developer notes</b></summary>

Defined in `src/configs/categories/general_category.py`.
</details>
</details>

### Window position and size _implemented_

Remember where the window opens and how big it is, using relative or absolute values.

<details>
<summary><b>How to use</b></summary>

Set `window_geometry.position` and `window_geometry.size`. Each has a `type` of `relative` or `absolute`, a "remember" option for position, and separate values for relative (percentage) and absolute (pixel) modes.

<details>
<summary><b>Developer notes</b></summary>

Defined in `src/configs/categories/window_geometry_category.py`, which can convert between relative and absolute coordinates.
</details>
</details>

### Every config as a command-line argument _implemented_

Any setting can be given on the command line.

<details>
<summary><b>How to use</b></summary>

For example, `--general.results_box.maximum_results 10`. The config parser accepts dotted setting names.

<details>
<summary><b>Developer notes</b></summary>

Enabled by `cli_parse_args` on the settings model, with unknown arguments ignored so the app's own parser still works.
</details>
</details>

### Settings window _in progress_

A proper window for editing settings instead of the file.

<details>
<summary><b>How to use</b></summary>

Not released yet. The design is a foldable category tree on the left and the active settings on the right, with live preview.

<details>
<summary><b>Developer notes</b></summary>

Work lives on the `settings-implementation` branch. Settings widgets come in categories and value types (checkbox, combo box, line edit, spin box, color edit, file and folder pickers), and can depend on or inherit from other settings.
</details>
</details>

### Config inheritance and dependencies _planned_

Let settings inherit values and show or hide based on other settings.

<details>
<summary><b>How to use</b></summary>

Planned as part of the settings window.

<details>
<summary><b>Developer notes</b></summary>

The config UI metadata already supports a `show` condition and `changed` hooks. Deeper inheritance and dependency rules are still open questions.
</details>
</details>

### Multiple config formats _planned_

Read the config from JSON or YAML as well as TOML.

<details>
<summary><b>How to use</b></summary>

Planned. Prospero would look for TOML first, then JSON, then YAML.

<details>
<summary><b>Developer notes</b></summary>

Would add more `pydantic-settings` sources.
</details>
</details>

---

## Window & UI

### Frameless, always-on-top window _implemented_

The window has no title bar and stays above other windows.

<details>
<summary><b>How to use</b></summary>

It looks and behaves this way automatically. `Esc` closes it; dragging the background moves it.

<details>
<summary><b>Developer notes</b></summary>

Uses `FramelessWindowHint`, `WindowStaysOnTopHint`, and a translucent background in `src/ui/main_window.py`.
</details>
</details>

### Rounded corners _implemented_

The window has smooth rounded corners.

<details>
<summary><b>How to use</b></summary>

Automatic.

<details>
<summary><b>Developer notes</b></summary>

Handled by a corner mask overlay (`src/ui/_corner_mas_overlay.py`).
</details>
</details>

### Open and close animation _implemented_

The window grows in and shrinks out with easing.

<details>
<summary><b>How to use</b></summary>

Automatic when you open or close it.

<details>
<summary><b>Developer notes</b></summary>

Width and height animations in `MainWindow`, plus an animated results layout (`src/shared_ui_elements/custom_vbox_layout.py`).
</details>
</details>

### Focused-result bar _implemented_

A small bar marks the currently selected result.

<details>
<summary><b>How to use</b></summary>

It follows the selected row as you move up and down.

<details>
<summary><b>Developer notes</b></summary>

`src/ui/_focused_result_bar.py`, positioned by the main window.
</details>
</details>

### Scroll to the focused result _implemented_

The list scrolls so the selected result is always visible.

<details>
<summary><b>How to use</b></summary>

Automatic when you navigate with the arrow keys.

<details>
<summary><b>Developer notes</b></summary>

`_scroll_results_if_needed()` in `src/ui/main_window.py` animates the scrollbar.
</details>
</details>

### Remember window position _implemented_

Reopen the window where you last put it.

<details>
<summary><b>How to use</b></summary>

Enable "remember" in `window_geometry.position`.

<details>
<summary><b>Developer notes</b></summary>

The position config is updated on drag and saved.
</details>
</details>

### Suggestions and autofill _planned_

Show a hint in the query box and complete it with a key.

<details>
<summary><b>How to use</b></summary>

Planned. A result would be able to suggest text (shown faintly in the query box) that `Tab` would accept.

<details>
<summary><b>Developer notes</b></summary>

The query box already renders a suggestion suffix, and results already have a `suggestion_request` field. The remaining work is wiring the autofill key.
</details>
</details>

### Result details on demand _planned_

Let a result reveal extra information such as its score.

<details>
<summary><b>How to use</b></summary>

Planned.

<details>
<summary><b>Developer notes</b></summary>

Would extend the result widget to expand and show more fields.
</details>
</details>

### Moving line on the focused result _planned_

Draw an animated line in front of the selected result.

<details>
<summary><b>How to use</b></summary>

Planned; the current focus bar is a simpler version.

<details>
<summary><b>Developer notes</b></summary>

A UI animation task related to the focus bar.
</details>
</details>

### Scroll long names and descriptions _planned_

Scroll text that is wider than the window.

<details>
<summary><b>How to use</b></summary>

Planned for long app names and descriptions.

<details>
<summary><b>Developer notes</b></summary>

A `ScrollingLabel` widget is designed on a development branch; it scrolls text back and forth when it overflows.
</details>
</details>

### Animated window position change _planned_

Move the window smoothly when its configured position changes.

<details>
<summary><b>How to use</b></summary>

Planned.

<details>
<summary><b>Developer notes</b></summary>

A UI animation task in the main window.
</details>
</details>

### Vertical open/close animation _planned_

Support animating in a vertical direction as well as horizontal.

<details>
<summary><b>How to use</b></summary>

Planned.

<details>
<summary><b>Developer notes</b></summary>

An extension of the current size animations.
</details>
</details>

### Focus polling _planned_

Make sure the window stays focused while it is open.

<details>
<summary><b>How to use</b></summary>

Planned. The window would check once a second and refocus itself (or close) if it lost focus.

<details>
<summary><b>Developer notes</b></summary>

Would add a timer and a Win32 focus check in the main window.
</details>
</details>

### Changelog after update _planned_

Show what changed after an automatic update.

<details>
<summary><b>How to use</b></summary>

Planned. On first launch after an update, the changelog would be shown.

<details>
<summary><b>Developer notes</b></summary>

Would use the release body already returned by the updater.
</details>
</details>

---

## Query Box

### Customizable placeholder _implemented_

Show live information in the empty query box.

<details>
<summary><b>How to use</b></summary>

The placeholder supports tokens wrapped in braces. A few examples:

```
{time:{HH}:{mm}:{ss}}
{app.name} v{app.version}
{system.cpu_usage}
```

<details>
<summary><b>Developer notes</b></summary>

Implemented in `src/ui/_query_box/_placeholder_formatter.py`. Tokens are registered through `src/query_placeholder_tokens.py` and can have an update interval, a fallback placeholder, and optional arguments.
</details>
</details>

### Time and date tokens _implemented_

Insert the current time and date.

<details>
<summary><b>How to use</b></summary>

Tokens such as `{YYYY}`, `{MM}`, `{DD}`, `{HH}`, `{mm}`, `{ss}`, `{SSS}`, `{dddd}` give date and time parts.

<details>
<summary><b>Developer notes</b></summary>

Built-in unit tokens in the placeholder formatter. Using `{SSS}` switches the refresh rate to every millisecond.
</details>
</details>

### App info tokens _implemented_

Show information about Prospero itself.

<details>
<summary><b>How to use</b></summary>

`{app.name}`, `{app.version}`, `{app.pid}`, `{app.uptime}`, and version parts like `{v.major}`.

<details>
<summary><b>Developer notes</b></summary>

Registered in the placeholder formatter from the app constants.
</details>
</details>

### System info tokens _implemented_

Show information about your computer.

<details>
<summary><b>How to use</b></summary>

`{system.os}`, `{system.arch}`, `{system.hostname}`, `{system.cpu_usage}`, `{system.memory_usage}`, `{system.battery}`, `{system.uptime}`, and `{system.network_status}`.

<details>
<summary><b>Developer notes</b></summary>

Uses `psutil` and platform calls inside the placeholder formatter.
</details>
</details>

### Unit tokens _implemented_

Format values as sizes, durations, and fractions.

<details>
<summary><b>How to use</b></summary>

Tokens such as `{size}` (human-readable size), `{d}` (duration), `{ff}`, `{f%}`, and `{fcf}` (fractions), and text helpers like `{lower}`, `{upper}`, `{title}`.

<details>
<summary><b>Developer notes</b></summary>

Defined as unit tokens in the placeholder formatter, applied to the preceding token or metric.
</details>
</details>

### Loading animation _implemented_

The query box shows an animated line while providers are working.

<details>
<summary><b>How to use</b></summary>

Automatic. It appears while results are loading and disappears when they are ready.

<details>
<summary><b>Developer notes</b></summary>

`src/ui/_query_box/query_box.py` draws a tapered arc along the bottom edge, synced to the screen refresh rate (capped at 120 fps).
</details>
</details>

### Result count token _implemented_

Insert the number of current results.

<details>
<summary><b>How to use</b></summary>

Use `{app.result_count}` in the placeholder.

<details>
<summary><b>Developer notes</b></summary>

Registered by the main window and updated whenever results change.
</details>
</details>

### Provider count token _planned_

Insert the number of providers that returned results.

<details>
<summary><b>How to use</b></summary>

Planned.

<details>
<summary><b>Developer notes</b></summary>

Would be a sibling of `app.result_count`.
</details>
</details>

### Query length token _planned_

Insert the length of the current query.

<details>
<summary><b>How to use</b></summary>

Planned.

<details>
<summary><b>Developer notes</b></summary>

Would register another placeholder token.
</details>
</details>

### Custom shell tokens _planned_

Fetch a token's value by running a shell command.

<details>
<summary><b>How to use</b></summary>

Planned. A token could run a command and show its output.

<details>
<summary><b>Developer notes</b></summary>

Would extend the token registration API.
</details>
</details>

### Query presets _planned_

Save and reuse favourite queries.

<details>
<summary><b>How to use</b></summary>

Planned.

<details>
<summary><b>Developer notes</b></summary>

Not designed in detail yet.
</details>
</details>

### Bind placeholder to config _planned_

Control the placeholder from the settings file.

<details>
<summary><b>How to use</b></summary>

Planned. The format string would be a normal setting, and the query box would stop refreshing when part of it is not in use.

<details>
<summary><b>Developer notes</b></summary>

Part of the customizable-placeholder work; needs the settings binding and the `updated` signal to fire only for tokens in use.
</details>
</details>

---

## Icons

### Icon loading _implemented_

Results show real icons loaded from the platform.

<details>
<summary><b>How to use</b></summary>

Automatic for app results.

<details>
<summary><b>Developer notes</b></summary>

`src/helpers/_fetch_icon.py` is a facade that picks the platform implementation. On Windows (`_fetch_icon_win.py`) icons come from the shell APIs, both from files and from packaged apps. On Linux (`_fetch_icon_unix.py`) the app provider already resolved the freedesktop icon name to a file, so it just loads the image. Different load methods are described by `IconLoadMethod` in `src/data_objects.py`.
</details>
</details>

### Loading spinner and default icon _implemented_

Show a spinner while an icon loads and a default icon if it fails.

<details>
<summary><b>How to use</b></summary>

Automatic.

<details>
<summary><b>Developer notes</b></summary>

`src/shared_ui_elements/icon.py` manages the icon state (default, loading, loaded) and animates the spinner.
</details>
</details>

### Icon caching _implemented_

Loaded icons are cached and reused.

<details>
<summary><b>How to use</b></summary>

Automatic; icons load faster the second time.

<details>
<summary><b>Developer notes</b></summary>

The icon widget keeps a cache with a timeout.
</details>
</details>

### Segoe icon support _planned_

Use the Windows Segoe icon font as another icon source.

<details>
<summary><b>How to use</b></summary>

Planned. This would add many ready-made icons for results and tokens.

<details>
<summary><b>Developer notes</b></summary>

Would add another load method to the icon system.
</details>
</details>

### Icon zoom animation _planned_

Animate an icon when it loads or changes.

<details>
<summary><b>How to use</b></summary>

Planned.

<details>
<summary><b>Developer notes</b></summary>

A UI animation task on the icon widget.
</details>
</details>

---

## Online, Updates & Offline

### Auto updater _implemented_

Check for new versions on GitHub and install them.

<details>
<summary><b>How to use</b></summary>

Use the `Updater` command. The latest release is fetched, downloaded, and (on Windows) the installer is launched quietly.

<details>
<summary><b>Developer notes</b></summary>

`src/updater.py` fetches the latest release from the GitHub API, downloads the first asset, verifies progress, and on Windows runs the installer with `/silent`, `/autostart`, and `/dir=...`. On Linux the download is skipped for installation because there is no Inno Setup equivalent yet — the update check still works, but installing is manual (download the new tarball and re-run `install.sh`).
</details>
</details>

### Custom update server _implemented_

Point updates at a mirror or different domain.

<details>
<summary><b>How to use</b></summary>

Pass `--update-domain <url>` on the command line.

<details>
<summary><b>Developer notes</b></summary>

The network client supports per-service base URL overrides (`set_base_url`). The updater applies the override for the `github` service.
</details>
</details>

### Offline mode _implemented_

Run without connecting to the internet.

<details>
<summary><b>How to use</b></summary>

Pass `--offline`. Fetches and downloads are refused while this is set.

<details>
<summary><b>Developer notes</b></summary>

`src/network/_client.py` checks an `offline` flag and returns an offline error instead of making requests.
</details>
</details>

### Network client _implemented_

One shared, safe way to make network requests.

<details>
<summary><b>How to use</b></summary>

No direct action; it powers updates and other network features.

<details>
<summary><b>Developer notes</b></summary>

`src/network/_client.py` wraps `QNetworkAccessManager` with a User-Agent header, timeouts, safe redirects, streaming downloads, and cancellation.
</details>
</details>

### Global offline enforcement _planned_

Make sure absolutely nothing online is attempted while offline.

<details>
<summary><b>How to use</b></summary>

Planned hardening of the offline flag.

<details>
<summary><b>Developer notes</b></summary>

Most paths already respect the flag; this is about closing the remaining gaps.
</details>
</details>

### Check-update argument _planned_

Add an argument that decides whether to check for updates on launch.

<details>
<summary><b>How to use</b></summary>

Planned, for example `--check-update true`.

<details>
<summary><b>Developer notes</b></summary>

Would be added to the argument parser and read at startup.
</details>
</details>

---

## Command Line

Prospero can be configured and launched from the command line. These arguments are implemented.

<details>
<summary><b>How to use</b></summary>

```
prospero [options]

-v, --version            print the version and exit
-c, --config <path>      use a specific config file
-d, --debug              enable debug logging and the debug provider
--cli                    run in the terminal instead of the window
--theme <path>           use one theme file for dark and light
--dark-theme <path>      set the dark theme file
--light-theme <path>     set the light theme file
--offline                never connect to the internet
--update-domain <url>    use a custom update server
```

<details>
<summary><b>Developer notes</b></summary>

Parsed with `argparse` in `src/arg_parser.py`. Unknown arguments are ignored so that the config's own command-line source can also read dotted setting names.
</details>
</details>

---

## Integrations

These connect Prospero to other tools. They are not built yet.

### Everything search _planned_

Use the Everything tool to search files quickly.

<details>
<summary><b>How to use</b></summary>

Planned as part of the file-system provider.

<details>
<summary><b>Developer notes</b></summary>

Would talk to Everything's SDK or its command-line interface.
</details>
</details>

### Clipboard monitoring _planned_

Watch the clipboard and offer quick actions for what it holds.

<details>
<summary><b>How to use</b></summary>

Planned. Copy something, then open Prospero to see suggested actions.

<details>
<summary><b>Developer notes</b></summary>

Would need a clipboard watcher and a provider that reacts to changes.
</details>
</details>

### Tags and aliases _planned_

Search results by tag or alias instead of only by name.

<details>
<summary><b>How to use</b></summary>

Planned. Typing a tag like `Power` would show all power-related commands.

<details>
<summary><b>Developer notes</b></summary>

Would add tags to results and include them in matching.
</details>
</details>

---

## Planned Providers

These providers are designed but not built yet (the color provider has some experimental work).

### File System Provider _planned_

Browse files and folders from the launcher.

<details>
<summary><b>How to use</b></summary>

Planned: search by any part of a path, see file details, multi-select with `,`, and open a file with an app.

<details>
<summary><b>Developer notes</b></summary>

Intended to use the Everything tool for search and the Windows registry for "Open With" details.
</details>
</details>

### Volume Provider _planned_

Adjust system and per-app volume.

<details>
<summary><b>How to use</b></summary>

Planned syntax like `Volume 5` or `<App Name> Volume 5`.

<details>
<summary><b>Developer notes</b></summary>

Would show a slider widget and control the Windows audio session.
</details>
</details>

### Color Provider _in progress_

Deal with colors: pick, convert, and mix them.

<details>
<summary><b>How to use</b></summary>

Planned features include a color wheel, mode conversion (for example hex to RGB), mixing colors, and a palette. Experimental code exists but is not on the main branch yet.

<details>
<summary><b>Developer notes</b></summary>

Built on the shared `src/color_calculator/` module, which uses `coloraide`.
</details>
</details>

### Terminal / Shell Provider _planned_

Run commands and watch their output live.

<details>
<summary><b>How to use</b></summary>

Planned: type a command and see standard output update in the result.

<details>
<summary><b>Developer notes</b></summary>

Would stream process output into a custom result widget.
</details>
</details>

### Share Provider _planned_

Share content to other apps, such as a messaging app.

<details>
<summary><b>How to use</b></summary>

Planned; the exact sharing targets are still being decided.

<details>
<summary><b>Developer notes</b></summary>

Depends on the inter-provider payload design.
</details>
</details>

### Lyrics Provider _planned_

Show lyrics for the song that is playing.

<details>
<summary><b>How to use</b></summary>

Planned. Would show lyrics as a result.

<details>
<summary><b>Developer notes</b></summary>

Would need a media-session reader and a lyrics source.
</details>
</details>

---

## Performance & Internals

### Multithreading _implemented_

Providers run in parallel instead of one after another.

<details>
<summary><b>How to use</b></summary>

Automatic; it is why the window stays fast.

<details>
<summary><b>Developer notes</b></summary>

A shared `ThreadPool` in `src/global_threading.py`.
</details>
</details>

### Incremental fuzzy matching _implemented_

Speed up matching by only re-checking survivors as you type.

<details>
<summary><b>How to use</b></summary>

Automatic.

<details>
<summary><b>Developer notes</b></summary>

`IncrementalMatcher` in `src/fuzzy_finder.py`.
</details>
</details>

### Optional dependency manager _in progress_

Install extra parts only when they are needed, with checks in place.

<details>
<summary><b>How to use</b></summary>

Not user-facing yet; it would let optional features pull in their own packages safely.

<details>
<summary><b>Developer notes</b></summary>

`src/package_manager/` installs only allow-listed, pinned packages, verifies their hashes, and loads them through a custom import finder.
</details>
</details>

### Lower memory use _planned_

Reduce how much memory the app uses.

<details>
<summary><b>How to use</b></summary>

Planned behind the scenes.

<details>
<summary><b>Developer notes</b></summary>

Goals include caching and reusing `QImage`/`QPixmap`, loading constants only when needed, and tracking and freeing Qt objects as soon as they are unused.
</details>
</details>

### Unique result identifier _planned_

Replace the current result id, which is a hash that can clash.

<details>
<summary><b>How to use</b></summary>

Internal. It would make results update and compare more reliably.

<details>
<summary><b>Developer notes</b></summary>

`BaseResult.__hash__` currently hashes text plus description.
</details>
</details>

### VIM mode _planned_

Edit the query with VIM-style keys.

<details>
<summary><b>How to use</b></summary>

Planned. Default mode would be Insert, with a Normal mode using `h`/`l`, `j`/`k`, `w`/`b`/`$`, `a`/`i`, `dd`, and more.

<details>
<summary><b>Developer notes</b></summary>

Would add a key-handling mode layer to the query box and results list.
</details>
</details>

### Multi-command _planned_

Run several commands from one query.

<details>
<summary><b>How to use</b></summary>

Planned. Like the calculator's `;`, but for actions.

<details>
<summary><b>Developer notes</b></summary>

Would extend the `;` handling to non-calculator results.
</details>
</details>

---

## Known Issues

These are bugs or rough edges that are still open.

<details>
<summary><b>Open issues</b></summary>

- Widgets inside layouts do not have antialiasing, so some animations look slightly rough.
- The hotkey does not trigger when an administrator application is focused.
- An icon can fall back to the default and reuse it from the cache without retrying a fetch.
- A memory leak can be reproduced by pressing `D`, then the left arrow, and repeating.
- A scientific number cannot have a unit attached.
- A percent number cannot have a unit attached.
- A constant next to a number can be misread (for example, `1pi` becomes a wrong number).
- Sometimes apps are not re-sorted by score when a query is typed before the app list has finished loading.

<details>
<summary><b>Developer notes</b></summary>

These are tracked in the project's `Todo.md` under "Known Issues". The antialiasing and icon-cache items are related to the custom result widgets and the icon loader.
</details>
</details>

---

## Future Ideas

Ideas that are interesting but not committed to yet.

<details>
<summary><b>Open ideas</b></summary>

- 3D graphs in the calculator (overkill, but fun).
- A small chart for `min` and `max` results.
- A share target picker.
- More token types for the placeholder.

<details>
<summary><b>Developer notes</b></summary>

These come from the project notes and are marked with a `?` or `[R]` status.
</details>
</details>

---

<p align="center"><a href="#prospero--feature-reference">Back to top</a></p>

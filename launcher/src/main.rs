#![cfg_attr(windows, windows_subsystem = "windows")]

#[cfg(not(windows))]
fn main() {
    eprintln!("ProsperoLauncher is a Windows-only helper.");
}

#[cfg(windows)]
fn main() {
    if let Err(error) = win::run() {
        win::show_error(&format!("Prospero could not start:\n\n{error}"));
    }
}

#[cfg(windows)]
mod win {
    use std::env;
    use std::ffi::OsStr;
    use std::fs;
    use std::io;
    use std::os::windows::ffi::OsStrExt;
    use std::os::windows::process::CommandExt;
    use std::path::{Path, PathBuf};
    use std::process::Command;
    use std::time::SystemTime;

    type Handle = isize;

    const SYNCHRONIZE: u32 = 0x0010_0000;
    const INFINITE: u32 = 0xFFFF_FFFF;
    const MOVEFILE_REPLACE_EXISTING: u32 = 0x0000_0001;
    const MOVEFILE_WRITE_THROUGH: u32 = 0x0000_0008;
    const CREATE_NEW_PROCESS_GROUP: u32 = 0x0000_0200;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    const MB_ICONERROR: u32 = 0x0000_0010;

    #[link(name = "kernel32")]
    extern "system" {
        fn OpenProcess(dw_desired_access: u32, b_inherit_handle: i32, dw_process_id: u32)
            -> Handle;
        fn WaitForSingleObject(h_handle: Handle, dw_milliseconds: u32) -> u32;
        fn CloseHandle(h_object: Handle) -> i32;
        fn MoveFileExW(existing: *const u16, new: *const u16, flags: u32) -> i32;
    }

    #[link(name = "user32")]
    extern "system" {
        fn MessageBoxW(hwnd: isize, text: *const u16, caption: *const u16, utype: u32) -> i32;
    }

    pub fn run() -> Result<(), String> {
        let executable = env::current_exe().map_err(|error| error.to_string())?;
        let root = executable
            .parent()
            .ok_or_else(|| "Launcher has no parent directory.".to_string())?;

        let mut wait_pid = None;
        let mut passthrough = Vec::new();
        let mut arguments = env::args_os().skip(1);
        while let Some(argument) = arguments.next() {
            if argument.as_os_str() == OsStr::new("--wait-pid") {
                if let Some(value) = arguments.next() {
                    wait_pid = value.to_string_lossy().parse::<u32>().ok();
                }
            } else {
                passthrough.push(argument);
            }
        }

        if let Some(pid) = wait_pid {
            wait_for_process(pid);
        }

        apply_pending(root);

        let version = resolved_version(root).ok_or_else(|| {
            "No installed version was found. Please reinstall Prospero.".to_string()
        })?;
        let application = app_executable(root, &version);
        if !application.is_file() {
            return Err(format!(
                "Version {version} is incomplete ({} is missing).",
                application.display()
            ));
        }

        let working_directory = application
            .parent()
            .ok_or_else(|| "Application path has no parent directory.".to_string())?;
        Command::new(&application)
            .args(&passthrough)
            .current_dir(working_directory)
            .creation_flags(CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW)
            .spawn()
            .map(|_| ())
            .map_err(|error| format!("Could not start {}: {error}", application.display()))
    }

    fn wait_for_process(pid: u32) {
        let handle = unsafe { OpenProcess(SYNCHRONIZE, 0, pid) };
        if handle == 0 {
            return;
        }
        unsafe {
            let _ = WaitForSingleObject(handle, INFINITE);
            let _ = CloseHandle(handle);
        }
    }

    fn apply_pending(root: &Path) {
        let pending = root.join("pending.txt");
        let Some(version) = read_version_file(&pending) else {
            if pending.exists() {
                let _ = fs::remove_file(&pending);
            }
            return;
        };

        if app_executable(root, &version).is_file() {
            if write_version_file(&root.join("current.txt"), &version).is_ok() {
                let _ = fs::remove_file(&pending);
            }
        } else {
            // Never trap the user in a boot loop because of an incomplete download.
            let _ = fs::remove_file(&pending);
        }
    }

    fn resolved_version(root: &Path) -> Option<String> {
        for name in ["current.txt", "previous.txt"] {
            if let Some(version) = read_version_file(&root.join(name)) {
                if app_executable(root, &version).is_file() {
                    return Some(version);
                }
            }
        }
        newest_version(root)
    }

    fn newest_version(root: &Path) -> Option<String> {
        let versions = root.join("versions");
        let entries = fs::read_dir(versions).ok()?;
        let mut newest: Option<(SystemTime, String)> = None;
        for entry in entries.flatten() {
            let Ok(file_type) = entry.file_type() else {
                continue;
            };
            if !file_type.is_dir() {
                continue;
            }
            let Some(version) = entry.file_name().to_str().map(str::to_owned) else {
                continue;
            };
            if !is_safe_version(&version) || !app_executable(root, &version).is_file() {
                continue;
            }
            let modified = entry
                .metadata()
                .and_then(|metadata| metadata.modified())
                .unwrap_or(SystemTime::UNIX_EPOCH);
            if newest.as_ref().map_or(true, |(time, _)| modified > *time) {
                newest = Some((modified, version));
            }
        }
        newest.map(|(_, version)| version)
    }

    fn app_executable(root: &Path, version: &str) -> PathBuf {
        root.join("versions")
            .join(version)
            .join("Prospero")
            .join("Prospero.exe")
    }

    fn read_version_file(path: &Path) -> Option<String> {
        let version = fs::read_to_string(path).ok()?.trim().to_string();
        if is_safe_version(&version) {
            Some(version)
        } else {
            None
        }
    }

    fn write_version_file(path: &Path, version: &str) -> io::Result<()> {
        let temporary = path.with_extension("tmp");
        fs::write(&temporary, version)?;
        move_file_replace(&temporary, path)
    }

    fn move_file_replace(from: &Path, to: &Path) -> io::Result<()> {
        let from = wide(from.as_os_str());
        let to = wide(to.as_os_str());
        let result = unsafe {
            MoveFileExW(
                from.as_ptr(),
                to.as_ptr(),
                MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH,
            )
        };
        if result == 0 {
            Err(io::Error::last_os_error())
        } else {
            Ok(())
        }
    }

    fn is_safe_version(version: &str) -> bool {
        !version.is_empty()
            && !version.starts_with('.')
            && version != "."
            && version != ".."
            && !version.contains("..")
            && version
                .chars()
                .all(|character| character.is_ascii_alphanumeric() || ".-_+!".contains(character))
    }

    fn wide(value: &OsStr) -> Vec<u16> {
        value.encode_wide().chain(std::iter::once(0)).collect()
    }

    pub fn show_error(message: &str) {
        let text = wide(OsStr::new(message));
        let caption = wide(OsStr::new("Prospero"));
        unsafe {
            let _ = MessageBoxW(0, text.as_ptr(), caption.as_ptr(), MB_ICONERROR);
        }
    }
}

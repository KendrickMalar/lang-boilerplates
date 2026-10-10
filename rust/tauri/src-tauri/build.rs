fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Register every custom app command here AND in the runtime invoke handler.
    // Empty is not a safe boundary for unregistered commands; see README.
    let app_manifest = tauri_build::AppManifest::new().commands(&[]);
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(app_manifest))?;
    Ok(())
}

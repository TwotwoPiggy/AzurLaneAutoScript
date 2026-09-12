import {app} from 'electron';

/**
 * Configure Chromium command line switches for low power consumption,
 * dedicated GPU offloading to Intel HD 4600 integrated GPU, and memory limits.
 *
 * Must be invoked before app.whenReady().
 */
export function configurePerformanceFlags(dpiScaling: boolean): void {
  // 1. Force route rendering to Integrated GPU (Intel HD 4600) and Direct3D 11
  // Disencumbers Nvidia GTX 960M 2GB VRAM completely for MuMu 12 / 3D game execution.
  app.commandLine.appendSwitch('gpu-preference', 'low-power');
  app.commandLine.appendSwitch('force_low_power_gpu');
  app.commandLine.appendSwitch('use-angle', 'd3d11');

  // 2. Disable unnecessary 3D pipelines while preserving 2D Canvas & DOM hardware composition
  app.commandLine.appendSwitch('disable-3d-apis');
  app.commandLine.appendSwitch('disable-webgl');
  app.commandLine.appendSwitch('disable-webgl2');

  // 3. Baseline frame rate cap to prevent uncapped rendering loops
  app.commandLine.appendSwitch('limit-fps', '30');

  // 4. Native window occlusion calculation
  // Enables Chromium to treat completely covered windows (e.g. Thorium fullscreen livestream) as occluded.
  app.commandLine.appendSwitch('enable-features', 'CalculateNativeWinOcclusion');

  // 5. V8 Heap memory constraint to mitigate 16GB RAM / 15.8GB PageFile pressure
  app.commandLine.appendSwitch('js-flags', '--max-old-space-size=128 --optimize-for-size --lite-mode');

  // 6. High DPI scaling configuration
  if (!dpiScaling) {
    app.commandLine.appendSwitch('high-dpi-support', '1');
    app.commandLine.appendSwitch('force-device-scale-factor', '1');
  }
}

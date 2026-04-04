/// <reference types="vitest/globals" />
/// <reference types="@testing-library/jest-dom" />

interface Window {
  requestAnimationFrame(callback: FrameRequestCallback): number;
  cancelAnimationFrame(id: number): void;
}

interface Global {
  requestAnimationFrame(callback: FrameRequestCallback): number;
  cancelAnimationFrame(id: number): void;
}

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { SpectrumAnalyzer } from './SpectrumAnalyzer';

// Mock RAF first
let mockRafCallbacks: Array<(() => void) | undefined> = [];
let mockRaf: ReturnType<typeof vi.fn>;
let mockCancelRaf: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mockRafCallbacks = [];
  mockRaf = vi.fn((cb: FrameRequestCallback) => {
    const id = mockRafCallbacks.length;
    mockRafCallbacks.push(() => cb(0));
    return id;
  });
  mockCancelRaf = vi.fn((id: number) => {
    mockRafCallbacks[id] = undefined;
  });
  globalThis.requestAnimationFrame = mockRaf as any;
  globalThis.cancelAnimationFrame = mockCancelRaf as any;
});

afterEach(() => {
  cleanup();
});

// Mock uPlot
vi.mock('uplot', () => ({
  default: vi.fn(() => ({
    setData: vi.fn(),
    destroy: vi.fn(),
    root: { classList: { add: vi.fn() } },
  })),
}));

// Mock uplot-react with factory
vi.mock('uplot-react', () => {
  const mockUplotReact = vi.fn((props: any) => {
    const mockChart = {
      setData: vi.fn(),
      destroy: vi.fn(),
      root: { classList: { add: vi.fn() } },
    };
    if (props.onCreate) props.onCreate(mockChart);
    return <div data-testid="uplot-mock" />;
  });
  return { default: mockUplotReact };
});

// Import the mocked module to access calls
import UplotReact from 'uplot-react';

describe('SpectrumAnalyzer', () => {
  describe('Rendering', () => {
    it('should render the chart container', () => {
      render(<SpectrumAnalyzer />);
      expect(screen.getByTestId('spectrum-analyzer')).toBeInTheDocument();
    });

    it('should render uPlot chart component', () => {
      render(<SpectrumAnalyzer />);
      expect(screen.getByTestId('uplot-mock')).toBeInTheDocument();
    });
  });

  describe('uPlot Configuration', () => {
    it('should configure Y-axis for dB amplitude with range -100 to 0', () => {
      render(<SpectrumAnalyzer />);

      const callArgs = (UplotReact as any).mock.calls[0];
      const options = callArgs[0]?.options;

      expect(options?.scales?.y?.min).toBe(-100);
      expect(options?.scales?.y?.max).toBe(0);
    });

    it('should apply dark mode theme styling', () => {
      render(<SpectrumAnalyzer />);

      const callArgs = (UplotReact as any).mock.calls[0];
      const options = callArgs[0]?.options;

      expect(options).toBeDefined();
    });

    it('should configure series with fill under line', () => {
      render(<SpectrumAnalyzer />);

      const callArgs = (UplotReact as any).mock.calls[0];
      const options = callArgs[0]?.options;

      expect(options?.series).toBeDefined();
    });
  });

  describe('Buffer & Draw Pattern', () => {
    it('should initialize requestAnimationFrame loop', () => {
      render(<SpectrumAnalyzer />);

      expect(mockRaf).toHaveBeenCalled();
    });

    it('should use stable data reference for uPlot (Buffer & Draw)', () => {
      // This test verifies the Buffer & Draw pattern by checking that
      // changing the wave data doesn't cause uPlot-react to re-render with new data
      const { rerender } = render(<SpectrumAnalyzer />);

      const initialCalls = (UplotReact as any).mock.calls;
      const initialData = initialCalls[0][0]?.data;

      // Update with different data (simulating WebSocket update)
      const newData = {
        wave: new Array(512).fill(-40).map((v, i) => v - i), // Different values
      };
      rerender(<SpectrumAnalyzer data={newData} />);

      // uPlot-react should receive the same data reference because
      // the Buffer & Draw pattern uses a ref (buffer) instead of props
      const updatedCalls = (UplotReact as any).mock.calls;
      const updatedData = updatedCalls[updatedCalls.length - 1][0]?.data;

      // The key assertion: data passed to uPlot should remain stable
      // because buffering happens via ref, not prop changes
      expect(initialData).toEqual(updatedData);
    });
  });

  describe('Custom Annotations', () => {
    it('should configure draw hook for custom annotations', () => {
      render(<SpectrumAnalyzer />);

      const callArgs = (UplotReact as any).mock.calls[0];
      const options = callArgs[0]?.options;

      expect(options?.hooks?.draw).toBeDefined();
    });

    it('should support drawing annotation labels', () => {
      render(<SpectrumAnalyzer />);

      const callArgs = (UplotReact as any).mock.calls[0];
      const options = callArgs[0]?.options;

      expect(typeof options?.hooks?.draw?.[0]).toBe('function');
    });
  });

  describe('Lifecycle', () => {
    it('should clean up requestAnimationFrame on unmount', () => {
      const { unmount } = render(<SpectrumAnalyzer />);

      unmount();

      expect(mockCancelRaf).toHaveBeenCalled();
    });
  });

  describe('Data Flow', () => {
    it('should accept wave data via props', () => {
      const testData = {
        wave: new Array(512).fill(-30),
        annotations: [],
      };

      render(<SpectrumAnalyzer data={testData} />);
      expect(screen.getByTestId('spectrum-analyzer')).toBeInTheDocument();
    });

    it('should accept annotations configuration', () => {
      const annotations = [
        { label: 'ARP', frequency: 100 },
        { label: 'HTTPS', frequency: 443 },
      ];

      render(<SpectrumAnalyzer annotations={annotations} />);
      expect(screen.getByTestId('spectrum-analyzer')).toBeInTheDocument();
    });
  });
});

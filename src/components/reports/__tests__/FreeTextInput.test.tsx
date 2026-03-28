import { render, screen, fireEvent, cleanup, act } from '@testing-library/react';
import FreeTextInput from '../FreeTextInput';

jest.mock('src/components/QueryString', () => ({
  setQueryStringValue: jest.fn(),
  getQueryStringValue: jest.fn()
}));

describe('FreeTextInput', () => {
  const defaultProps = {
    inputId: 'test-input',
    inputDefault: { label: 'default', value: 'default' },
    labelName: 'Test Label',
    value: {},
    setValue: jest.fn()
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
    cleanup();
  });

  it('renders a text field with the given label', () => {
    render(<FreeTextInput {...defaultProps} />);
    expect(screen.getByLabelText('Test Label')).toBeInTheDocument();
  });

  it('initialises with the inputDefault value', () => {
    render(<FreeTextInput {...defaultProps} />);
    expect(screen.getByLabelText('Test Label')).toHaveValue('default');
  });

  it('does not call setValue immediately on change (debounced)', () => {
    render(<FreeTextInput {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Test Label'), {
      target: { value: 'new value' }
    });
    expect(defaultProps.setValue).not.toHaveBeenCalled();
  });

  it('calls setValue with updated value after debounce delay', () => {
    render(<FreeTextInput {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Test Label'), {
      target: { value: 'new value' }
    });
    act(() => { jest.advanceTimersByTime(300); });
    expect(defaultProps.setValue).toHaveBeenCalledWith({
      'test-input': { label: '', value: 'new value' }
    });
  });

  it('calls setValue with inputDefault when the field is cleared', () => {
    render(<FreeTextInput {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Test Label'), {
      target: { value: '' }
    });
    act(() => { jest.advanceTimersByTime(300); });
    expect(defaultProps.setValue).toHaveBeenCalledWith({
      'test-input': { label: 'default', value: 'default' }
    });
  });

  it('only fires setValue once for rapid keystrokes (debounce collapses them)', () => {
    render(<FreeTextInput {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Test Label'), { target: { value: 'a' } });
    fireEvent.change(screen.getByLabelText('Test Label'), { target: { value: 'ab' } });
    fireEvent.change(screen.getByLabelText('Test Label'), { target: { value: 'abc' } });
    act(() => { jest.advanceTimersByTime(300); });
    expect(defaultProps.setValue).toHaveBeenCalledTimes(1);
    expect(defaultProps.setValue).toHaveBeenCalledWith({
      'test-input': { label: '', value: 'abc' }
    });
  });
});

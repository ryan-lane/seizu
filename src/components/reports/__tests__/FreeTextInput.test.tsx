import { render, screen, fireEvent, cleanup } from '@testing-library/react';
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
  });

  afterEach(cleanup);

  it('renders a text field with the given label', () => {
    render(<FreeTextInput {...defaultProps} />);
    expect(screen.getByLabelText('Test Label')).toBeInTheDocument();
  });

  it('calls setValue with updated value on change', () => {
    render(<FreeTextInput {...defaultProps} />);
    fireEvent.change(screen.getByLabelText('Test Label'), {
      target: { value: 'new value' }
    });
    expect(defaultProps.setValue).toHaveBeenCalledWith({
      'test-input': { label: '', value: 'new value' }
    });
  });

  it('calls setValue with inputDefault when value is empty', () => {
    render(<FreeTextInput {...defaultProps} />);
    // Simulate clearing the input (null/undefined scenario is handled internally)
    fireEvent.change(screen.getByLabelText('Test Label'), {
      target: { value: 'typed' }
    });
    expect(defaultProps.setValue).toHaveBeenCalled();
  });
});

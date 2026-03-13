import { render, screen, fireEvent } from '@testing-library/react';
import AuthDialog from '../AuthDialog';

jest.mock('use-neo4j', () => ({
  createDriver: jest.fn()
}));

const { createDriver } = require('use-neo4j');

const defaultProps = {
  setAuth: jest.fn(),
  setDriver: jest.fn(),
  neo4jSettings: {
    protocol: 'bolt',
    hostname: 'localhost',
    port: 7687,
    authMode: 'native'
  }
};

describe('AuthDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the dialog with title', () => {
    render(<AuthDialog {...defaultProps} />);
    expect(screen.getByText('Log into Neo4j')).toBeInTheDocument();
  });

  it('renders username and password fields', () => {
    render(<AuthDialog {...defaultProps} />);
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });

  it('renders submit button', () => {
    render(<AuthDialog {...defaultProps} />);
    expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
  });

  it('calls setAuth and createDriver on submit', () => {
    const mockDriver = { verifyConnectivity: jest.fn().mockResolvedValue(undefined) };
    createDriver.mockReturnValue(mockDriver);

    render(<AuthDialog {...defaultProps} />);

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: 'testuser' }
    });
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'testpass' }
    });
    fireEvent.click(screen.getByRole('button', { name: /submit/i }));

    expect(defaultProps.setAuth).toHaveBeenCalledWith({
      username: 'testuser',
      password: 'testpass'
    });
    expect(createDriver).toHaveBeenCalledWith(
      'bolt',
      'localhost',
      7687,
      'testuser',
      'testpass'
    );
  });

  it('submits on Enter key press in username field', () => {
    const mockDriver = { verifyConnectivity: jest.fn().mockResolvedValue(undefined) };
    createDriver.mockReturnValue(mockDriver);

    render(<AuthDialog {...defaultProps} />);

    fireEvent.change(screen.getByLabelText(/username/i), {
      target: { value: 'testuser' }
    });
    fireEvent.keyDown(screen.getByLabelText(/username/i), { keyCode: 13 });

    expect(defaultProps.setAuth).toHaveBeenCalled();
  });

  it('shows error message when authentication fails', async () => {
    const mockDriver = {
      verifyConnectivity: jest.fn().mockRejectedValue(new Error('Auth failed'))
    };
    createDriver.mockReturnValue(mockDriver);

    render(<AuthDialog {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: /submit/i }));

    // Wait for the promise rejection to propagate
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.getByText(/authentication failed/i)).toBeInTheDocument();
  });
});

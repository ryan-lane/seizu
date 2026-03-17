import { GlobalRegistrator } from '@happy-dom/global-registrator';
// Set a desktop viewport so MUI media queries (e.g. breakpoints.down('lg'))
// don't fire and hide components during tests.
GlobalRegistrator.register({ width: 1920, height: 1080 });

import '@testing-library/jest-dom';

import { TextEncoder, TextDecoder } from 'util';

(global as Record<string, unknown>).TextEncoder = TextEncoder;
(global as Record<string, unknown>).TextDecoder = TextDecoder;

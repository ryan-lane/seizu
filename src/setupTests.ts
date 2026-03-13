import { GlobalRegistrator } from '@happy-dom/global-registrator';
GlobalRegistrator.register();

import '@testing-library/jest-dom';

import { TextEncoder, TextDecoder } from 'util';

(global as Record<string, unknown>).TextEncoder = TextEncoder;
(global as Record<string, unknown>).TextDecoder = TextDecoder;

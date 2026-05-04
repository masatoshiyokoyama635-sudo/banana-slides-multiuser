import { describe, expect, it } from 'vitest';
import { apiClient } from '@/api/client';

describe('apiClient auth config', () => {
  it('sends session cookies with API requests', () => {
    expect(apiClient.defaults.withCredentials).toBe(true);
  });
});

import test from 'node:test'
import assert from 'node:assert/strict'

import { shouldSuppressGlobalError } from '../src/utils/requestPolicy.js'

test('request policy suppresses only explicitly expected capability errors', () => {
  const expected = {
    config: { suppressErrorCodes: ['new_authority_required'] },
    response: { data: { detail: { error_code: 'new_authority_required' } } },
  }
  const unexpected = {
    config: { suppressErrorCodes: ['new_authority_required'] },
    response: { data: { detail: { error_code: 'database_busy' } } },
  }

  assert.equal(shouldSuppressGlobalError(expected), true)
  assert.equal(shouldSuppressGlobalError(unexpected), false)
  assert.equal(shouldSuppressGlobalError({ config: { suppressGlobalError: true } }), true)
  assert.equal(shouldSuppressGlobalError(new Error('offline')), false)
})

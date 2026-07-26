export function shouldSuppressGlobalError(error) {
  const errorCode = error?.response?.data?.detail?.error_code
  const suppressedCodes = error?.config?.suppressErrorCodes || []
  return error?.config?.suppressGlobalError === true || suppressedCodes.includes(errorCode)
}

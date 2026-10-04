// A small client for a Hamilton server's dashboard API.

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

export function client({ url, token }) {
  async function call(path, { method = 'GET', body } = {}) {
    let response
    try {
      response = await fetch(`${url}/api/admin${path}`, {
        method,
        headers: {
          authorization: `Bearer ${token}`,
          ...(body === undefined ? {} : { 'content-type': 'application/json' }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    } catch (error) {
      throw new ApiError(0, `could not reach ${url} (${error.cause?.code ?? error.message})`)
    }
    if (!response.ok) {
      let detail = `the server answered ${response.status}`
      try {
        const parsed = await response.json()
        if (typeof parsed.detail === 'string') detail = parsed.detail
      } catch {
        /* keep the generic message */
      }
      if (response.status === 401) detail = 'the admin token was not accepted'
      if (response.status === 404 && path === '/pack') {
        detail = 'this server has no dashboard API; start it with --admin'
      }
      throw new ApiError(response.status, detail)
    }
    return response.json()
  }

  return {
    pack: () => call('/pack'),
    overview: () => call('/overview'),
    saveSection: (section, values) => call(`/pack/${section}`, { method: 'PUT', body: values }),
    saveKnowledge: (name, text) =>
      call(`/knowledge/${encodeURIComponent(name)}`, { method: 'PUT', body: { text } }),
    deleteKnowledge: (name) => call(`/knowledge/${encodeURIComponent(name)}`, { method: 'DELETE' }),
    runTests: () => call('/sim', { method: 'POST', body: {} }),
    records: (type) => call(`/records${type ? `?type=${encodeURIComponent(type)}` : ''}`),
    setRecordStatus: (id, status) =>
      call(`/records/${encodeURIComponent(id)}`, { method: 'PATCH', body: { status } }),
    conversations: () => call('/conversations'),
    conversation: (id) => call(`/conversations/${encodeURIComponent(id)}`),
  }
}

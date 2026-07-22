export const SETTINGS_PRESETS = [
  { id: 'timely', label: '及时', description: '更快发现变化', pollInterval: 10, monitorInterval: 1 },
  { id: 'balanced', label: '均衡', description: '适合日常使用', pollInterval: 30, monitorInterval: 5 },
  { id: 'efficient', label: '省资源', description: '降低刷新频率', pollInterval: 60, monitorInterval: 15 },
]

export function detectSettingsPreset(pollInterval, monitorInterval) {
  return SETTINGS_PRESETS.find(item => item.pollInterval === Number(pollInterval) && item.monitorInterval === Number(monitorInterval))?.id || 'custom'
}

export function settingsForPreset(id) {
  const preset = SETTINGS_PRESETS.find(item => item.id === id)
  return preset ? { pollInterval: preset.pollInterval, monitorInterval: preset.monitorInterval } : null
}

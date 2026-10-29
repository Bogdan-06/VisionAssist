import { sessionConfiguration } from './session.mjs';

export function geminiTokenConfiguration(model = 'gemini-3.8-live', now = Date.now()) {
  return {
    uses: 1,
    expireTime: new Date(now + 10 * 60_000).toISOString(),
    newSessionExpireTime: new Date(now + 60_000).toISOString(),
    // Raw REST schema. Lock the entire setup; mobile clients cannot override it.
    bidiGenerateContentSetup: {
      model: `models/${model}`,
      generationConfig: { responseModalities: ['AUDIO'] },
      systemInstruction: { parts: [{ text: sessionConfiguration().session.instructions }] },
      realtimeInputConfig: {
        automaticActivityDetection: { disabled: false },
        activityHandling: 'START_OF_ACTIVITY_INTERRUPTS'
      },
      tools: [{ functionDeclarations: [{ name: 'request_camera_image',
        description: 'Request one photo only after an explicit visual question. Wait for phone confirmation; never assume permission.',
        parameters: { type: 'OBJECT', properties: {} } }] }]
    }
  };
}

import { useState, useRef, useCallback } from 'react'

const SUPPORTED_MIME = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/ogg',
  'audio/mp4',
]

function getSupportedMimeType() {
  return SUPPORTED_MIME.find(t => MediaRecorder.isTypeSupported(t)) || ''
}

export function useRecorder(maxSeconds = 120) {
  const [recording, setRecording]   = useState(false)
  const [audioBlob, setAudioBlob]   = useState(null)
  const [duration, setDuration]     = useState(0)
  const [error, setError]           = useState(null)

  const mediaRef    = useRef(null)
  const chunksRef   = useRef([])
  const timerRef    = useRef(null)
  const startTimeRef = useRef(null)

  const start = useCallback(async () => {
    setError(null)
    setAudioBlob(null)
    setDuration(0)
    chunksRef.current = []

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = getSupportedMimeType()
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {})

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType || 'audio/webm' })
        setAudioBlob(blob)
        stream.getTracks().forEach(t => t.stop())
      }

      recorder.start(250) // collect every 250ms
      mediaRef.current  = recorder
      startTimeRef.current = Date.now()
      setRecording(true)

      // Auto-stop after maxSeconds
      timerRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000)
        setDuration(elapsed)
        if (elapsed >= maxSeconds) stop()
      }, 500)
    } catch (err) {
      setError(err.message || 'Microphone access denied')
    }
  }, [maxSeconds])

  const stop = useCallback(() => {
    if (mediaRef.current && mediaRef.current.state !== 'inactive') {
      mediaRef.current.stop()
    }
    clearInterval(timerRef.current)
    setRecording(false)
    setDuration(d => d)
  }, [])

  const reset = useCallback(() => {
    stop()
    setAudioBlob(null)
    setDuration(0)
    setError(null)
  }, [stop])

  return { recording, audioBlob, duration, error, start, stop, reset }
}

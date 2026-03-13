import { useState, useCallback, useRef, useEffect } from 'react'

const STORAGE_KEY = 'burndown-sound-enabled'

function getInitialState(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored === null ? true : stored === 'true'
  } catch {
    return true
  }
}

export type SoundEffect =
  | 'fanfare'
  | 'celebration'
  | 'airhorn'
  | 'drumroll'
  | 'yankee-doodle'
  | 'curb'
  | 'say-so'
  | 'outro'
  | 'team-totals'
  | 'tokens-podium'
  | 'milestones'

const SOUND_URLS: Record<SoundEffect, string> = {
  fanfare: '/sounds/fanfare.mp3',
  celebration: '/sounds/celebration.mp3',
  airhorn: '/sounds/airhorn.mp3',
  drumroll: '/sounds/drumroll.mp3',
  'yankee-doodle': '/sounds/yankee-doodle.mp3',
  curb: '/sounds/curb.mp3',
  'say-so': '/sounds/say-so.mp3',
  outro: '/sounds/outro.mp3',
  'team-totals': '/sounds/team-totals.mp3',
  'tokens-podium': '/sounds/tokens-podium.mp3',
  milestones: '/sounds/milestones.mp3',
}

export function useSoundEffects() {
  const [enabled, setEnabled] = useState(getInitialState)
  const activeAudios = useRef<HTMLAudioElement[]>([])

  const toggle = useCallback(() => {
    setEnabled((prev) => {
      const next = !prev
      localStorage.setItem(STORAGE_KEY, String(next))
      if (!next) {
        // Stop all playing sounds when muting
        for (const audio of activeAudios.current) {
          audio.pause()
          audio.currentTime = 0
        }
        activeAudios.current = []
      }
      return next
    })
  }, [])

  const play = useCallback(
    (effect: SoundEffect, options?: { volume?: number; delay?: number; loop?: boolean }) => {
      if (!enabled) return

      const doPlay = () => {
        const audio = new Audio(SOUND_URLS[effect])
        audio.volume = options?.volume ?? 0.5
        audio.loop = options?.loop ?? false
        activeAudios.current.push(audio)
        audio.addEventListener('ended', () => {
          activeAudios.current = activeAudios.current.filter((a) => a !== audio)
        })
        audio.play().catch(() => {
          // Browser may block autoplay — that's fine
        })
        return audio
      }

      if (options?.delay) {
        setTimeout(doPlay, options.delay)
        return undefined
      }
      return doPlay()
    },
    [enabled],
  )

  const stopAll = useCallback(() => {
    for (const audio of activeAudios.current) {
      audio.pause()
      audio.currentTime = 0
    }
    activeAudios.current = []
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      for (const audio of activeAudios.current) {
        audio.pause()
      }
      activeAudios.current = []
    }
  }, [])

  return { enabled, toggle, play, stopAll }
}

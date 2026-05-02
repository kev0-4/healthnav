import { useState, useEffect } from 'react'

export function useGeolocation() {
  const [location, setLocation] = useState(null) // { lat, lng }
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!navigator.geolocation) {
      setError('Geolocation not supported')
      setLoading(false)
      return
    }
    navigator.geolocation.getCurrentPosition(
      pos => {
        setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setLoading(false)
      },
      err => {
        setError(err.message)
        setLoading(false)
      },
      { timeout: 8000, maximumAge: 300_000 }, // cache position for 5 min
    )
  }, [])

  return { location, loading, error }
}

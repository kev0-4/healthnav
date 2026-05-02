import { useState, useEffect } from 'react'
import { MapPin, Shield, Building2, Award, Hospital, ChevronRight, Navigation } from 'lucide-react'
import HospitalSheet from './HospitalSheet'
import { useGeolocation } from '../hooks/useGeolocation'
import { fetchOsrmDistances, fetchHospitalReviews } from '../api'

function fmt(n) { return `₹${n.toLocaleString('en-IN')}` }

const TYPE_LABELS = { government: 'Government', mid_private: 'Mid-Private', corporate: 'Corporate' }
const TYPE_COLORS = {
  government:  { badge: 'text-blue-300 bg-blue-950 border-blue-900',   bar: 'from-blue-600 to-blue-400' },
  mid_private: { badge: 'text-teal-300 bg-teal-950 border-teal-900',   bar: 'from-teal-600 to-teal-400' },
  corporate:   { badge: 'text-purple-300 bg-purple-950 border-purple-900', bar: 'from-purple-600 to-purple-400' },
}

function TypeIcon({ type }) {
  if (type === 'government') return <Building2 size={12} className="text-blue-400" />
  if (type === 'corporate')  return <Award size={12} className="text-purple-400" />
  return <Hospital size={12} className="text-teal-400" />
}

function Stars({ rating, loading }) {
  if (loading) return (
    <div className="flex items-center gap-0.5">
      {[1,2,3,4,5].map(i => (
        <div key={i} className="w-[11px] h-[11px] rounded-sm animate-pulse" style={{ background: '#1E2D45' }} />
      ))}
      <span className="text-slate-600 text-[12px] ml-1">fetching…</span>
    </div>
  )
  if (!rating) return <span className="text-slate-600 text-[12px]">No rating</span>
  return (
    <div className="flex items-center gap-0.5">
      {[1,2,3,4,5].map(i => (
        <svg key={i} width="11" height="11" viewBox="0 0 24 24" fill={i <= Math.round(rating) ? '#F59E0B' : '#1E2D45'}>
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
        </svg>
      ))}
      <span className="text-slate-400 text-[12px] ml-1">{rating.toFixed(1)}</span>
    </div>
  )
}

function parseSpecialties(raw) {
  if (!raw || raw === '0') return []
  if (Array.isArray(raw)) return raw
  return raw.split(',').map(s => s.trim()).filter(Boolean)
}

function fmtDist(km) {
  if (km == null) return null
  return km < 1 ? `${Math.round(km * 1000)} m` : `${km} km`
}
function fmtTime(mins) {
  if (mins == null) return null
  if (mins < 60) return `${mins} min`
  return `${Math.floor(mins / 60)} h ${mins % 60} min`
}

export default function TabHospitals({ hospitals, baseCost, city }) {
  const [selected, setSelected]   = useState(null)
  const [filter, setFilter]       = useState('All Types')
  const [distances, setDistances]   = useState({})
  const [ratings, setRatings]       = useState({})    // hospital_id → number
  const [loadingRatings, setLoadingRatings] = useState(new Set())

  const { location } = useGeolocation()

  useEffect(() => {
    if (!location || !hospitals.length) return
    fetchOsrmDistances(location.lat, location.lng, hospitals)
      .then(setDistances)
  }, [location, hospitals])

  // Fetch ratings for all hospitals in parallel (cache-backed — instant if seen before)
  useEffect(() => {
    if (!hospitals.length) return
    hospitals.forEach(h => {
      const id = h.hospital_id
      if (!id || h.rating_google) return  // already have a DB rating, skip
      setLoadingRatings(prev => new Set([...prev, id]))
      fetchHospitalReviews(id, h.name, h.address).then(data => {
        if (data?.rating) setRatings(prev => ({ ...prev, [id]: data.rating }))
        setLoadingRatings(prev => { const s = new Set(prev); s.delete(id); return s })
      })
    })
  }, [hospitals])

  const maxRange = Math.max(...hospitals.map(h => h.range[1]))

  const getRating = h => ratings[h.hospital_id] ?? h.rating_google ?? null

  const filtered = hospitals.filter(h => {
    if (filter === '⭐ 4.0+') return (getRating(h) ?? 0) >= 4.0
    if (filter === '🛡 NABH') return h.nabh
    return true
  })

  return (
    <div className="p-6 max-w-5xl">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-white font-bold text-lg">Matched Providers</h3>
          <p className="text-slate-500 text-sm mt-0.5">{city || 'Your city'} · Sorted by best match</p>
        </div>

        {/* Filter pills */}
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {['All Types', '⭐ 4.0+', '🛡 NABH'].map((f) => (
            <button key={f} onClick={() => setFilter(f)}
              className={`text-[11px] px-3 py-1.5 rounded-full border transition-colors ${f === filter ? 'bg-blue-600 border-blue-500 text-white' : 'border-[#1E2D45] text-slate-400 hover:border-slate-500'}`}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12 text-slate-500 text-sm">
          No hospitals match this filter.{' '}
          <button onClick={() => setFilter('All Types')} className="text-blue-400 hover:text-blue-300">Show all</button>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {filtered.map((h, i) => {
          const tc      = TYPE_COLORS[h.type] || TYPE_COLORS.mid_private
          const barWidth = (h.range[1] / maxRange) * 100
          const specs   = parseSpecialties(h.specialties)
          const hid     = h.hospital_id ?? i
          const travel  = distances[hid] ?? {}
          const rating  = getRating(h)
          const ratingLoading = !h.rating_google && loadingRatings.has(h.hospital_id)

          return (
            <div key={hid}
              className="rounded-2xl p-5 transition-all cursor-pointer hover:translate-y-[-2px] hover:shadow-lg"
              style={{
                background: '#0D1525',
                border: `1px solid ${i === 0 ? '#2563EB55' : '#1E2D45'}`,
                boxShadow: i === 0 ? '0 0 20px rgba(37,99,235,0.08)' : 'none',
              }}
              onClick={() => setSelected({ ...h, _specs: specs, ...travel, rating_google: rating ?? h.rating_google })}>

              {/* Header */}
              <div className="flex items-start justify-between gap-3 mb-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-2">
                    {i === 0 && (
                      <span className="text-[10px] font-bold uppercase tracking-widest bg-blue-600 text-white px-2.5 py-1 rounded-full">
                        Top Match
                      </span>
                    )}
                    <span className={`text-[10px] font-bold uppercase tracking-widest border px-2.5 py-1 rounded-full ${tc.badge}`}>
                      {TYPE_LABELS[h.type]}
                    </span>
                    {h.nabh && (
                      <span className="flex items-center gap-1 text-[10px] text-green-400 bg-green-950 border border-green-900 px-2 py-0.5 rounded-full font-semibold">
                        <Shield size={9} /> NABH
                      </span>
                    )}
                  </div>
                  <h4 className="text-white font-bold text-[16px] leading-tight mb-2">{h.name}</h4>
                  <div className="flex items-center gap-4 text-[12px] text-slate-500 flex-wrap">
                    <Stars rating={rating} loading={ratingLoading} />
                    {travel.dist_km != null
                      ? <span className="flex items-center gap-1 text-teal-400">
                          <Navigation size={10} />{fmtDist(travel.dist_km)}
                          {travel.travel_mins != null && <span className="text-slate-500 ml-0.5">· {fmtTime(travel.travel_mins)}</span>}
                        </span>
                      : location
                        ? <span className="flex items-center gap-1 text-slate-600"><MapPin size={10} />No route</span>
                        : <span className="flex items-center gap-1 text-slate-600"><MapPin size={10} />Locating…</span>
                    }
                    <span className="flex items-center gap-1"><TypeIcon type={h.type} />{h.beds} beds</span>
                  </div>

                  {/* Specialty tags */}
                  {specs.length > 0 && (
                    <div className="flex gap-1.5 mt-3 flex-wrap">
                      {specs.slice(0, 4).map(s => (
                        <span key={s} className="text-[10px] text-slate-500 bg-[#111C30] border border-[#1E2D45] px-2 py-0.5 rounded-full">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Cost */}
                <div className="text-right shrink-0">
                  <p className="text-[10px] text-slate-500 mb-1">{h.mult}× multiplier</p>
                  <p className="text-[22px] font-bold text-white leading-none">{fmt(h.range[0])}</p>
                  <p className="text-slate-400 text-[13px] mt-0.5">– {fmt(h.range[1])}</p>
                </div>
              </div>

              {/* Cost bar */}
              <div className="h-1.5 bg-[#111C30] rounded-full overflow-hidden mb-4">
                <div className={`h-full rounded-full bg-gradient-to-r ${tc.bar}`}
                  style={{ width: `${barWidth}%` }} />
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between">
                <p className="text-[11px] text-slate-600 truncate max-w-[260px]">{h.address}</p>
                <button className="flex items-center gap-1 text-blue-400 hover:text-blue-300 text-[12px] font-medium transition-colors shrink-0">
                  View details <ChevronRight size={13} />
                </button>
              </div>
            </div>
          )
        })}
      </div>

      <HospitalSheet hospital={selected} baseCost={baseCost} onClose={() => setSelected(null)} />
    </div>
  )
}

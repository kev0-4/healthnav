import { useEffect, useState } from 'react'
import { X, MapPin, Phone, Shield, AlertCircle, Globe, ExternalLink, Loader2, Navigation, Clock } from 'lucide-react'
import { fetchHospitalReviews } from '../api'

function fmt(n) { return `₹${n.toLocaleString('en-IN')}` }

const TYPE_LABELS = { government: 'Government', mid_private: 'Mid-Private', corporate: 'Corporate' }
const TYPE_COLORS = {
  government:  'text-blue-300 bg-blue-950 border-blue-900',
  mid_private: 'text-teal-300 bg-teal-950 border-teal-900',
  corporate:   'text-purple-300 bg-purple-950 border-purple-900',
}

function Stars({ rating, size = 13 }) {
  if (!rating) return <span className="text-slate-600 text-[13px]">No rating</span>
  return (
    <div className="flex items-center gap-0.5">
      {[1,2,3,4,5].map(i => (
        <svg key={i} width={size} height={size} viewBox="0 0 24 24"
          fill={i <= Math.round(rating) ? '#F59E0B' : '#1E2D45'}>
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
        </svg>
      ))}
      <span className="text-slate-300 text-[13px] font-semibold ml-1">{rating.toFixed(1)}</span>
    </div>
  )
}


export default function HospitalSheet({ hospital, baseCost, onClose }) {
  const [reviewsState, setReviewsState] = useState({ status: 'idle', data: null })

  useEffect(() => {
    if (!hospital) { setReviewsState({ status: 'idle', data: null }); return }
    setReviewsState({ status: 'loading', data: null })
    const id = hospital.hospital_id || hospital.name || ''
    fetchHospitalReviews(id, hospital.name, hospital.address)
      .then(data => setReviewsState({ status: 'done', data }))
      .catch(() => setReviewsState({ status: 'error', data: null }))
  }, [hospital?.hospital_id])

  if (!hospital) return null

  const typeClass = TYPE_COLORS[hospital.type] || TYPE_COLORS.mid_private
  const specs = hospital._specs || []
  const phone = hospital.mobile || hospital.telephone
  const cleanPhone = phone && phone !== '0' ? phone : null

  const distKm     = hospital.dist_km     ?? null
  const travelMins = hospital.travel_mins ?? null

  const lat = parseFloat(hospital.latitude)
  const lng = parseFloat(hospital.longitude)
  const hasCoords = !isNaN(lat) && !isNaN(lng) && lat !== 0 && lng !== 0
  const mapSrc = hasCoords
    ? `https://maps.google.com/maps?q=${lat},${lng}&z=15&output=embed&hl=en`
    : `https://maps.google.com/maps?q=${encodeURIComponent((hospital.name || '') + ' ' + (hospital.address || ''))}&output=embed&hl=en`

  const googleMapsLink = hasCoords
    ? `https://www.google.com/maps?q=${lat},${lng}`
    : `https://www.google.com/maps/search/${encodeURIComponent((hospital.name || '') + ' ' + (hospital.address || ''))}`

  const costRows = baseCost ? [
    ['Procedure Base', baseCost.procedure],
    ['Hospital Stay', baseCost.stay],
    ['Medications', baseCost.medication],
    ['Contingency', baseCost.contingency],
  ] : []

  const gRating      = reviewsState.data?.rating || hospital.rating_google
  const totalRatings = reviewsState.data?.total_ratings
  const sourceTitle  = reviewsState.data?.source_title || null
  const sourceUrl    = reviewsState.data?.source_url || null
  const googleMapsUrl = reviewsState.data?.google_maps_url || null

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-40 backdrop-blur-sm" onClick={onClose} />

      <div className="fixed right-0 top-0 h-full w-full md:w-[460px] z-50 flex flex-col overflow-y-auto"
        style={{ background: '#0D1525', borderLeft: '1px solid #1E2D45' }}>

        {/* Header */}
        <div className="flex items-start gap-3 p-5 border-b border-[#1E2D45] sticky top-0 z-10"
          style={{ background: '#0D1525' }}>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1.5">
              <span className={`text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full border ${typeClass}`}>
                {TYPE_LABELS[hospital.type]}
              </span>
              {hospital.nabh && (
                <span className="flex items-center gap-1 text-[10px] text-green-400 bg-green-950 border border-green-900 px-2.5 py-1 rounded-full font-semibold">
                  <Shield size={9} /> NABH
                </span>
              )}
            </div>
            <h2 className="text-white font-bold text-[17px] leading-tight">{hospital.name}</h2>
            {hospital.address && (
              <p className="flex items-start gap-1.5 text-slate-500 text-[12px] mt-1">
                <MapPin size={11} className="shrink-0 mt-0.5" />{hospital.address}
              </p>
            )}
          </div>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-[#1E2D45] transition-colors shrink-0">
            <X size={18} className="text-slate-400" />
          </button>
        </div>

        <div className="flex-1 p-5 space-y-4">

          {/* Distance + travel time */}
          {(distKm != null || travelMins != null) && (
            <div className="flex gap-3">
              {distKm != null && (
                <div className="flex-1 rounded-xl p-3 flex items-center gap-2.5"
                  style={{ background: '#111C30', border: '1px solid #1E2D45' }}>
                  <Navigation size={14} className="text-teal-400 shrink-0" />
                  <div>
                    <p className="text-[10px] text-slate-600 uppercase tracking-widest">Distance</p>
                    <p className="text-white font-bold text-[15px] leading-none mt-0.5">
                      {distKm < 1 ? `${Math.round(distKm * 1000)} m` : `${distKm} km`}
                    </p>
                  </div>
                </div>
              )}
              {travelMins != null && (
                <div className="flex-1 rounded-xl p-3 flex items-center gap-2.5"
                  style={{ background: '#111C30', border: '1px solid #1E2D45' }}>
                  <Clock size={14} className="text-blue-400 shrink-0" />
                  <div>
                    <p className="text-[10px] text-slate-600 uppercase tracking-widest">Drive time</p>
                    <p className="text-white font-bold text-[15px] leading-none mt-0.5">
                      {travelMins < 60
                        ? `${travelMins} min`
                        : `${Math.floor(travelMins / 60)} h ${travelMins % 60} min`}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Map widget */}
          <div className="rounded-2xl overflow-hidden" style={{ border: '1px solid #1E2D45' }}>
            <iframe
              title="Hospital location"
              src={mapSrc}
              width="100%"
              height="200"
              style={{ border: 0, display: 'block' }}
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
            />
          </div>

          {/* Ratings */}
          <div className="rounded-2xl p-4" style={{ background: '#111C30', border: '1px solid #1E2D45' }}>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-3">Ratings</p>

            {reviewsState.status === 'loading' && (
              <div className="flex items-center gap-2 py-3 text-slate-600 text-[12px]">
                <Loader2 size={13} className="animate-spin" /> Fetching ratings…
              </div>
            )}

            {reviewsState.status !== 'loading' && (
              <div className="flex items-center justify-between">
                <div>
                  {gRating ? (
                    <>
                      <Stars rating={gRating} size={15} />
                      {totalRatings && (
                        <p className="text-slate-600 text-[11px] mt-1">
                          {typeof totalRatings === 'number'
                            ? totalRatings.toLocaleString()
                            : totalRatings} ratings
                          {sourceTitle && <span> · {sourceTitle.replace(/\s*[-–|].*$/, '')}</span>}
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="text-slate-600 text-[13px]">No rating data found</p>
                  )}
                </div>
                <div className="flex flex-col gap-1.5 items-end">
                  {googleMapsUrl && (
                    <a href={googleMapsUrl} target="_blank" rel="noreferrer"
                      className="flex items-center gap-1.5 text-[11px] text-blue-400 hover:text-blue-300 transition-colors">
                      Google Maps <ExternalLink size={10} />
                    </a>
                  )}
                  {sourceUrl && (
                    <a href={sourceUrl} target="_blank" rel="noreferrer"
                      className="flex items-center gap-1.5 text-[11px] text-teal-400 hover:text-teal-300 transition-colors">
                      Read reviews <ExternalLink size={10} />
                    </a>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Hospital Details */}
          <div className="rounded-2xl p-4" style={{ background: '#111C30', border: '1px solid #1E2D45' }}>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-4">Hospital Details</p>
            <div className="grid grid-cols-2 gap-x-6 gap-y-3">
              {[
                ['Type', TYPE_LABELS[hospital.type] || 'N/A'],
                ['Total Beds', hospital.beds ?? 'N/A'],
                ['Emergency', hospital.emergency ? '✓ Available' : '—'],
                ['District', hospital.district || 'N/A'],
                ['State', hospital.state || 'N/A'],
                ['Pincode', hospital.pincode || 'N/A'],
                ['NABH', hospital.nabh ? 'Accredited ✓' : 'Not accredited'],
                ['Score', hospital.score ? `${(hospital.score * 100).toFixed(0)}%` : 'N/A'],
              ].map(([k, v]) => (
                <div key={k}>
                  <p className="text-[11px] text-slate-600 mb-0.5">{k}</p>
                  <p className="text-slate-300 text-[13px] font-medium">{v}</p>
                </div>
              ))}
            </div>

            {(hospital.website || hospital.mobile || hospital.telephone) && (
              <div className="mt-4 pt-3 border-t border-[#1E2D45] space-y-2">
                {hospital.website && (
                  <div className="flex items-center gap-2">
                    <Globe size={12} className="text-slate-600 shrink-0" />
                    <a href={hospital.website.startsWith('http') ? hospital.website : `https://${hospital.website}`}
                      target="_blank" rel="noreferrer"
                      className="text-blue-400 hover:text-blue-300 text-[12px] truncate transition-colors">
                      {hospital.website.replace(/^https?:\/\/(www\.)?/, '')}
                    </a>
                  </div>
                )}
                {cleanPhone && (
                  <div className="flex items-center gap-2">
                    <Phone size={12} className="text-slate-600 shrink-0" />
                    <span className="text-slate-400 text-[12px]">{cleanPhone}</span>
                  </div>
                )}
              </div>
            )}

            {specs.length > 0 && (
              <div className="mt-4 pt-3 border-t border-[#1E2D45]">
                <p className="text-[11px] text-slate-600 mb-2">Specialties</p>
                <div className="flex flex-wrap gap-1.5">
                  {specs.slice(0, 8).map(s => (
                    <span key={s} className="text-[11px] text-slate-400 bg-[#0D1525] border border-[#1E2D45] px-2.5 py-1 rounded-full">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Cost Estimate */}
          <div className="rounded-2xl p-4" style={{ background: '#111C30', border: '1px solid #1E2D45' }}>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold mb-4">
              Cost Estimate — {hospital.multiplier_low}–{hospital.multiplier_high}× multiplier
            </p>
            {costRows.length > 0 && (
              <div className="space-y-2 mb-4">
                {costRows.map(([label, base]) => (
                  <div key={label} className="flex justify-between text-[12px]">
                    <span className="text-slate-500">{label}</span>
                    <div className="text-right">
                      <span className="text-slate-700 line-through text-[11px] mr-2">{fmt(base[0])}</span>
                      <span className="text-slate-300 font-medium">
                        {fmt(Math.round(base[0] * hospital.multiplier_low))} – {fmt(Math.round(base[1] * hospital.multiplier_high))}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <div className="border-t border-[#1E2D45] pt-3 flex justify-between items-center">
              <span className="text-slate-400 text-sm font-medium">Adjusted Total</span>
              <div className="text-right">
                <p className="text-white font-bold text-[17px]">{fmt(hospital.range[0])} – {fmt(hospital.range[1])}</p>
                <p className="text-[11px] text-slate-600">{hospital.multiplier_low}–{hospital.multiplier_high}× applied</p>
              </div>
            </div>
          </div>

          <div className="rounded-xl p-4 flex items-start gap-3" style={{ background: '#0A1628', border: '1px solid #1E3A5F' }}>
            <AlertCircle size={13} className="text-blue-400 shrink-0 mt-0.5" />
            <p className="text-blue-300 text-[12px] leading-relaxed">
              This hospital may be eligible for <strong>AB-PMJAY Ayushman Bharat</strong> cashless treatment. Confirm empanelment directly with the hospital.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-[#1E2D45] flex gap-2.5">
          <a href={googleMapsUrl || googleMapsLink} target="_blank" rel="noreferrer"
            className="flex-1 flex items-center justify-center gap-2 text-slate-300 border border-[#1E2D45] hover:border-slate-500 rounded-xl py-2.5 text-[13px] font-medium transition-colors">
            <MapPin size={13} /> Directions
          </a>
          {cleanPhone ? (
            <a href={`tel:${cleanPhone}`}
              className="flex-1 flex items-center justify-center gap-2 text-slate-300 border border-[#1E2D45] hover:border-slate-500 rounded-xl py-2.5 text-[13px] font-medium transition-colors">
              <Phone size={13} /> Call
            </a>
          ) : (
            <button disabled
              className="flex-1 flex items-center justify-center gap-2 text-slate-700 border border-[#1E2D4560] rounded-xl py-2.5 text-[13px] font-medium cursor-not-allowed">
              <Phone size={13} /> No Phone
            </button>
          )}
          {hospital.website && (
            <a href={hospital.website.startsWith('http') ? hospital.website : `https://${hospital.website}`}
              target="_blank" rel="noreferrer"
              className="flex-1 flex items-center justify-center gap-2 text-slate-300 border border-[#1E2D45] hover:border-slate-500 rounded-xl py-2.5 text-[13px] font-medium transition-colors">
              <Globe size={13} /> Website
            </a>
          )}
        </div>
      </div>
    </>
  )
}

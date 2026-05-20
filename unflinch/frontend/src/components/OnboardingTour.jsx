import React, { useState, useEffect } from 'react'
import { Zap, Mic, BarChart2, ChevronRight, X } from 'lucide-react'

const STEPS = [
  {
    icon: '🎯',
    title: 'Welcome to Unflinch',
    desc: 'AI-powered mock interviews with real voice analysis. Practice until you\'re unstoppable.',
    color: 'text-ember',
  },
  {
    icon: '🧑‍💼',
    title: 'Set Up Your Interview',
    desc: 'Enter your target company and role. Pick a persona — Friendly HR, Strict Tech, Startup Founder, or Stress Interviewer.',
    color: 'text-azure',
  },
  {
    icon: '🎙️',
    title: 'Record Your Answers',
    desc: 'Answer 5 AI-generated questions by voice. We analyse your fillers, pauses, speech rate, and answer content in real time.',
    color: 'text-jade',
  },
  {
    icon: '⚡',
    title: 'Quick Drill Mode',
    desc: 'Short on time? Hit Quick Drill for a 5-question daily warmup. Perfect before a real interview.',
    color: 'text-amber',
  },
  {
    icon: '📊',
    title: 'Track Your Progress',
    desc: 'View your weakness tracker, filler word breakdown, and nervousness score trend. Watch yourself improve over time.',
    color: 'text-violet',
  },
]

export default function OnboardingTour({ onComplete }) {
  const [step, setStep] = useState(0)
  const current = STEPS[step]
  const isLast  = step === STEPS.length - 1

  return (
    <div className="fixed inset-0 bg-obsidian/95 backdrop-blur-sm z-50 flex items-center justify-center p-6 animate-fade-in">
      {/* Skip */}
      <button
        className="absolute top-6 right-6 text-mist hover:text-chalk transition-colors flex items-center gap-1 text-sm"
        onClick={onComplete}
      >
        <X size={16} /> Skip tour
      </button>

      <div className="max-w-sm w-full animate-slide-up">
        {/* Step dots */}
        <div className="flex justify-center gap-2 mb-8">
          {STEPS.map((_, i) => (
            <div key={i} className={`h-1.5 rounded-full transition-all duration-300
              ${i === step ? 'w-6 bg-ember' : i < step ? 'w-3 bg-ember/40' : 'w-3 bg-steel'}`} />
          ))}
        </div>

        {/* Content */}
        <div className="card text-center border-steel/80" key={step}>
          <div className="text-6xl mb-4">{current.icon}</div>
          <h2 className={`heading-display text-3xl mb-3 ${current.color}`}>{current.title}</h2>
          <p className="text-mist text-sm leading-relaxed mb-8">{current.desc}</p>

          <button
            className="btn-primary w-full flex items-center justify-center gap-2 py-4"
            onClick={() => isLast ? onComplete() : setStep(s => s + 1)}
          >
            {isLast ? '🚀 Let\'s Go!' : <>Next <ChevronRight size={16} /></>}
          </button>
        </div>
      </div>
    </div>
  )
}
import { useState, useEffect } from 'react'
import './App.css'

interface LogEntry {
  time: string
  level: 'info' | 'agent' | 'sandbox' | 'success' | 'error'
  message: string
}

interface FixtureMeta {
  id: string
  name: string
  language: string
  difficulty: string
  description: string
  reproduce_cmd: string
  target_file: string
}

const SAMPLE_FIXTURE: FixtureMeta = {
  id: 'sample-calculator-bug',
  name: 'Calculator Division & Zero Handling Bug',
  language: 'python',
  difficulty: 'beginner',
  description: 'The divide function uses integer floor division (//) instead of floating division (/), truncating negative quotients and failing precision tests.',
  reproduce_cmd: 'python -m unittest discover -s fixtures/bugs/sample-calculator-bug -p "test_*.py"',
  target_file: 'calc.py'
}

export function App() {
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'standalone'>('checking')
  const [selectedFixture, setSelectedFixture] = useState<string>('sample-calculator-bug')
  const [reproduceCmd, setReproduceCmd] = useState<string>(SAMPLE_FIXTURE.reproduce_cmd)
  const [issueDesc, setIssueDesc] = useState<string>(SAMPLE_FIXTURE.description)
  
  // Pipeline State
  const [isRunning, setIsRunning] = useState<boolean>(false)
  const [currentStep, setCurrentStep] = useState<number>(0)
  const [activeTab, setActiveTab] = useState<'telemetry' | 'diff' | 'sandbox' | 'manifest'>('telemetry')

  // Telemetry Log Feed
  const [logs, setLogs] = useState<LogEntry[]>([
    { time: '14:20:01', level: 'info', message: 'Repomedic dashboard initialized in monorepo environment' },
    { time: '14:20:02', level: 'info', message: 'Loaded benchmark fixtures from /fixtures/bugs/' },
    { time: '14:20:03', level: 'agent', message: 'Awaiting diagnosis trigger. Ready for autonomous repair cycle.' }
  ])

  // Check backend health on mount
  useEffect(() => {
    fetch('http://localhost:8000/api/v1/health')
      .then(res => res.json())
      .then(data => {
        if (data.status === 'healthy') {
          setBackendStatus('connected')
        } else {
          setBackendStatus('standalone')
        }
      })
      .catch(() => {
        setBackendStatus('standalone')
      })
  }, [])

  const startDiagnosis = () => {
    if (isRunning) return
    setIsRunning(true)
    setCurrentStep(1)
    setActiveTab('telemetry')

    const newLogs: LogEntry[] = [
      { time: new Date().toLocaleTimeString(), level: 'info', message: `Initializing session for fixture: ${selectedFixture}` },
      { time: new Date().toLocaleTimeString(), level: 'agent', message: 'Cloning repository workspace into ephemeral sandbox layer...' },
    ]
    setLogs(newLogs)

    // Simulate Agent Step 1 -> 2: Bug Reproduction
    setTimeout(() => {
      setCurrentStep(2)
      setLogs(prev => [
        ...prev,
        { time: new Date().toLocaleTimeString(), level: 'sandbox', message: `$ ${reproduceCmd}` },
        { time: new Date().toLocaleTimeString(), level: 'error', message: 'FAIL: test_divide_fractional (AssertionError: 2 != 2.5)' },
        { time: new Date().toLocaleTimeString(), level: 'error', message: 'FAIL: test_divide_negative_fractional (AssertionError: -4 != -3.5)' },
        { time: new Date().toLocaleTimeString(), level: 'agent', message: 'Bug successfully reproduced! 2 tests failing. Proceeding to fault localization...' }
      ])
    }, 1200)

    // Simulate Agent Step 2 -> 3: Fault Localization
    setTimeout(() => {
      setCurrentStep(3)
      setLogs(prev => [
        ...prev,
        { time: new Date().toLocaleTimeString(), level: 'agent', message: 'Executing tool: grep_search("def divide")' },
        { time: new Date().toLocaleTimeString(), level: 'info', message: 'Matched calc.py:22 -> "return a // b"' },
        { time: new Date().toLocaleTimeString(), level: 'agent', message: 'Fault isolated to calc.py:22. Floor division // truncates float quotient.' }
      ])
    }, 2400)

    // Simulate Agent Step 3 -> 4: Patch Synthesis
    setTimeout(() => {
      setCurrentStep(4)
      setLogs(prev => [
        ...prev,
        { time: new Date().toLocaleTimeString(), level: 'agent', message: 'Synthesizing candidate patch: Replace // with / floating division' },
        { time: new Date().toLocaleTimeString(), level: 'info', message: 'Generated unified diff for calc.py. Applying patch to sandbox...' }
      ])
    }, 3600)

    // Simulate Agent Step 4 -> 5: Verification in Sandbox
    setTimeout(() => {
      setCurrentStep(5)
      setIsRunning(false)
      setLogs(prev => [
        ...prev,
        { time: new Date().toLocaleTimeString(), level: 'sandbox', message: `$ ${reproduceCmd} [VERIFICATION]` },
        { time: new Date().toLocaleTimeString(), level: 'success', message: 'Ran 7 tests in 0.002s. OK (All 7 passed!)' },
        { time: new Date().toLocaleTimeString(), level: 'success', message: 'Verification PASSED: Patch validated against full test suite.' }
      ])
    }, 4800)
  }

  const resetSession = () => {
    setIsRunning(false)
    setCurrentStep(0)
    setLogs([
      { time: new Date().toLocaleTimeString(), level: 'info', message: 'Session reset. Ready for next diagnosis run.' }
    ])
  }

  return (
    <div className="dashboard-container">
      {/* Top Header */}
      <header className="header">
        <div className="brand-section">
          <div className="brand-icon">🩺</div>
          <div>
            <div className="brand-title">
              Repomedic
              <span className="version-badge">v0.1.0-alpha</span>
            </div>
            <div className="brand-subtitle">Autonomous Software Debugging & Verification Platform</div>
          </div>
        </div>

        <div className="header-actions">
          <div className="status-pill">
            <span className={`status-dot ${backendStatus === 'connected' ? 'online' : 'standalone'}`} />
            <span>
              {backendStatus === 'connected' ? 'FastAPI Connected' : 'Frontend Standalone Mode'}
            </span>
          </div>

          <a href="#docs" className="nav-link-btn" onClick={(e) => { e.preventDefault(); setActiveTab('manifest') }}>
            <span>Architecture & Contract</span>
          </a>
          <button className="nav-link-btn" onClick={resetSession}>
            <span>Reset</span>
          </button>
        </div>
      </header>

      {/* Metric Cards Row */}
      <section className="metrics-grid">
        <div className="metric-card">
          <div className="metric-title">
            <span>Repository Monorepo</span>
            <span>Foundation</span>
          </div>
          <div className="metric-value">feat/project-foundation</div>
          <div className="metric-bar"><div className="metric-progress" style={{ width: '100%' }} /></div>
        </div>

        <div className="metric-card">
          <div className="metric-title">
            <span>Bug Fixtures</span>
            <span>Available</span>
          </div>
          <div className="metric-value">
            1 <span className="metric-sub">Active Benchmark</span>
          </div>
          <div className="metric-bar"><div className="metric-progress" style={{ width: '100%', background: 'linear-gradient(90deg, #3b82f6, #06b6d4)' }} /></div>
        </div>

        <div className="metric-card">
          <div className="metric-title">
            <span>Sandbox Isolation</span>
            <span>Execution Layer</span>
          </div>
          <div className="metric-value">Docker Ready</div>
          <div className="metric-bar"><div className="metric-progress" style={{ width: '100%', background: 'linear-gradient(90deg, #8b5cf6, #ec4899)' }} /></div>
        </div>

        <div className="metric-card">
          <div className="metric-title">
            <span>Agent Repair Status</span>
            <span>Workflow</span>
          </div>
          <div className="metric-value">
            {currentStep === 5 ? 'Verified ✓' : isRunning ? 'Diagnosing...' : 'Idle'}
          </div>
          <div className="metric-bar">
            <div
              className="metric-progress"
              style={{
                width: `${(currentStep / 5) * 100}%`,
                background: currentStep === 5 ? '#10b981' : '#06b6d4'
              }}
            />
          </div>
        </div>
      </section>

      {/* Main Grid: Control Panel + Live Workspace */}
      <main className="main-grid">
        {/* Left Column: Launchpad Controls */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polygon points="10 8 16 12 10 16 10 8" />
              </svg>
              Diagnosis Launchpad
            </span>
          </div>

          <div className="panel-body">
            <div className="form-group">
              <label className="form-label">
                <span>Target Bug Benchmark</span>
                <span style={{ color: 'var(--accent-cyan)' }}>fixtures/bugs/</span>
              </label>
              <select
                className="form-select"
                value={selectedFixture}
                onChange={(e) => setSelectedFixture(e.target.value)}
                disabled={isRunning}
              >
                <option value="sample-calculator-bug">sample-calculator-bug (Python)</option>
                <option value="custom">Custom External Repository...</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">
                <span>Reproduction Command</span>
                <span style={{ color: 'var(--text-muted)' }}>Sandbox CLI</span>
              </label>
              <input
                type="text"
                className="form-input mono-input"
                value={reproduceCmd}
                onChange={(e) => setReproduceCmd(e.target.value)}
                disabled={isRunning}
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                <span>Bug Symptoms / Issue Description</span>
              </label>
              <textarea
                className="form-textarea"
                value={issueDesc}
                onChange={(e) => setIssueDesc(e.target.value)}
                disabled={isRunning}
              />
            </div>

            <button
              className="btn-primary"
              onClick={startDiagnosis}
              disabled={isRunning}
            >
              {isRunning ? (
                <>
                  <span className="status-dot online pulsing" />
                  Running Autonomous Diagnosis...
                </>
              ) : currentStep === 5 ? (
                'Run Diagnosis Again'
              ) : (
                'Start Autonomous Diagnosis'
              )}
            </button>

            <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', lineHeight: '1.4' }}>
              💡 Repomedic will run the reproduction test inside an isolated environment, localize the fault, apply a synthesized diff, and verify resolution.
            </div>
          </div>
        </div>

        {/* Right Column: Interactive Pipeline & Live Inspection */}
        <div className="panel">
          {/* Stepper Pipeline */}
          <div className="stepper-container">
            <div className={`step-item ${currentStep >= 1 ? (currentStep > 1 ? 'completed' : 'active') : ''}`}>
              <div className="step-num">{currentStep > 1 ? '✓' : '1'}</div>
              <span>Inspect Workspace</span>
            </div>
            <div className="step-divider" />
            <div className={`step-item ${currentStep >= 2 ? (currentStep > 2 ? 'completed' : 'active') : ''}`}>
              <div className="step-num">{currentStep > 2 ? '✓' : '2'}</div>
              <span>Reproduce Bug</span>
            </div>
            <div className="step-divider" />
            <div className={`step-item ${currentStep >= 3 ? (currentStep > 3 ? 'completed' : 'active') : ''}`}>
              <div className="step-num">{currentStep > 3 ? '✓' : '3'}</div>
              <span>Fault Localization</span>
            </div>
            <div className="step-divider" />
            <div className={`step-item ${currentStep >= 4 ? (currentStep > 4 ? 'completed' : 'active') : ''}`}>
              <div className="step-num">{currentStep > 4 ? '✓' : '4'}</div>
              <span>Synthesize Patch</span>
            </div>
            <div className="step-divider" />
            <div className={`step-item ${currentStep >= 5 ? 'completed' : ''}`}>
              <div className="step-num">{currentStep >= 5 ? '✓' : '5'}</div>
              <span>Verify Sandbox</span>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="tabs-nav">
            <button
              className={`tab-btn ${activeTab === 'telemetry' ? 'active' : ''}`}
              onClick={() => setActiveTab('telemetry')}
            >
              Agent Telemetry ({logs.length})
            </button>
            <button
              className={`tab-btn ${activeTab === 'diff' ? 'active' : ''}`}
              onClick={() => setActiveTab('diff')}
            >
              Synthesized Diff {currentStep >= 4 && <span style={{ color: 'var(--accent-emerald)' }}>●</span>}
            </button>
            <button
              className={`tab-btn ${activeTab === 'sandbox' ? 'active' : ''}`}
              onClick={() => setActiveTab('sandbox')}
            >
              Sandbox Terminal
            </button>
            <button
              className={`tab-btn ${activeTab === 'manifest' ? 'active' : ''}`}
              onClick={() => setActiveTab('manifest')}
            >
              Fixture & Specs
            </button>
          </div>

          {/* Tab Contents */}
          {activeTab === 'telemetry' && (
            <div className="terminal-view">
              {logs.map((log, index) => (
                <div key={index} className="terminal-line">
                  <span className="log-time">{log.time}</span>
                  <span className={`log-level ${log.level}`}>[{log.level.toUpperCase()}]</span>
                  <span className="log-msg">{log.message}</span>
                </div>
              ))}
            </div>
          )}

          {activeTab === 'diff' && (
            <div className="terminal-view">
              {currentStep < 4 ? (
                <div style={{ color: 'var(--text-muted)', padding: '24px 0', textAlign: 'center' }}>
                  No patch generated yet. Click "Start Autonomous Diagnosis" to synthesize a verified diff.
                </div>
              ) : (
                <div className="diff-viewer">
                  <div className="diff-file-header">
                    diff --git a/fixtures/bugs/sample-calculator-bug/calc.py b/fixtures/bugs/sample-calculator-bug/calc.py
                  </div>
                  <div className="diff-line context">@@ -18,7 +18,7 @@ def divide(a: float, b: float) -&gt; float:</div>
                  <div className="diff-line context">     if b == 0:</div>
                  <div className="diff-line context">         raise ValueError("Cannot divide by zero")</div>
                  <div className="diff-line deletion">-    return a // b  # BUG: should be a / b</div>
                  <div className="diff-line addition">+    return a / b   # FIXED: floating-point division</div>
                  <div className="diff-line context"> </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'sandbox' && (
            <div className="terminal-view">
              <div style={{ color: 'var(--accent-cyan)', marginBottom: '8px' }}>
                [SANDBOX] Docker Container: repomedic-sandbox-python:latest
              </div>
              <div style={{ color: 'var(--text-secondary)' }}>
                $ {reproduceCmd}
              </div>
              <br />
              {currentStep < 2 ? (
                <div style={{ color: 'var(--text-muted)' }}>Ready to run reproduction command.</div>
              ) : currentStep < 5 ? (
                <div style={{ color: '#fca5a5' }}>
                  FAIL: test_divide_fractional (test_calc.TestCalculator)<br />
                  AssertionError: 2 != 2.5 within 7 places (0.5 difference)<br /><br />
                  FAIL: test_divide_negative_fractional (test_calc.TestCalculator)<br />
                  AssertionError: -4 != -3.5 within 7 places (0.5 difference)<br /><br />
                  FAILED (failures=2)
                </div>
              ) : (
                <div>
                  <div style={{ color: '#fca5a5', textDecoration: 'line-through', opacity: 0.5 }}>
                    FAILED (failures=2)
                  </div>
                  <div style={{ color: 'var(--accent-emerald)', marginTop: '8px' }}>
                    ...............................................<br />
                    Ran 7 tests in 0.002s<br /><br />
                    OK (All 7 unit tests passed after patch verification!)
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'manifest' && (
            <div className="terminal-view">
              <div style={{ color: 'var(--accent-violet)', fontWeight: 600, marginBottom: '8px' }}>
                Fixture Metadata: {SAMPLE_FIXTURE.name}
              </div>
              <pre style={{ color: 'var(--text-secondary)', fontSize: '11.5px' }}>
{JSON.stringify(SAMPLE_FIXTURE, null, 2)}
              </pre>
              <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Documentation References:</span>
                <ul style={{ paddingLeft: '20px', marginTop: '6px', color: 'var(--accent-cyan)' }}>
                  <li>docs/architecture.md</li>
                  <li>docs/api-contract.md</li>
                  <li>fixtures/bugs/README.md</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App

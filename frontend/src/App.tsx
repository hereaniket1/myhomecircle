const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export default function App() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">FastAPI + Postgres + React</p>
        <h1>myhomecircle</h1>
        <p className="lede">
          A clean single-page application scaffold with a backend API, database, and frontend shell
          ready for real product work.
        </p>
      </section>

      <section className="panel">
        <h2>Ready points</h2>
        <ul>
          <li>API health endpoint</li>
          <li>Database configuration</li>
          <li>Docker Compose orchestration</li>
          <li>Typed React starter</li>
        </ul>
      </section>

      <section className="panel">
        <h2>API base URL</h2>
        <code>{apiBaseUrl}</code>
      </section>
    </main>
  )
}

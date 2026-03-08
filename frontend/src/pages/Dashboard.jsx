import { Outlet } from 'react-router-dom'
import Navbar from '../components/Navbar'

function Dashboard() {
  return (
    <div className="min-h-screen bg-gray-50/50">
      <Navbar />
      <main className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="page-enter">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

export default Dashboard

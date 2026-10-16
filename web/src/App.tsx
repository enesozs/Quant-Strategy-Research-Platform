import { lazy, Suspense } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router'
import { AppShell } from '@/components/shell/AppShell'
import { Skeleton } from '@/components/ui/Skeleton'

const ComparePage = lazy(() => import('@/pages/compare/ComparePage'))
const BacktestPage = lazy(() => import('@/pages/backtest/BacktestPage'))
const OptimizePage = lazy(() => import('@/pages/optimize/OptimizePage'))
const ValidateLayout = lazy(() => import('@/pages/validate/ValidateLayout'))
const SplitPage = lazy(() => import('@/pages/validate/SplitPage'))
const WalkForwardPage = lazy(() => import('@/pages/validate/WalkForwardPage'))
const PairsLayout = lazy(() => import('@/pages/pairs/PairsLayout'))
const PairsResearchPage = lazy(() => import('@/pages/pairs/ResearchPage'))
const PairsDiscoverPage = lazy(() => import('@/pages/pairs/DiscoverPage'))
const PairsPortfolioPage = lazy(() => import('@/pages/pairs/PortfolioPage'))
const GuidePage = lazy(() => import('@/pages/guide/GuidePage'))
const StrategyDetailPage = lazy(() => import('@/pages/guide/StrategyDetailPage'))

function Fallback() {
  return (
    <div className="mx-auto max-w-[1600px] space-y-4 px-4 py-8 sm:px-6 lg:px-8">
      <Skeleton className="h-7 w-56" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <Skeleton className="mt-6 h-96 w-full rounded-xl" />
    </div>
  )
}

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route
          element={
            <Suspense fallback={<Fallback />}>
              <Outlet />
            </Suspense>
          }
        >
          <Route index element={<Navigate to="/compare" replace />} />
          <Route path="compare" element={<ComparePage />} />
          <Route path="backtest" element={<BacktestPage />} />
          <Route path="optimize" element={<OptimizePage />} />
          <Route path="validate" element={<ValidateLayout />}>
            <Route index element={<SplitPage />} />
            <Route path="walk-forward" element={<WalkForwardPage />} />
          </Route>
          <Route path="pairs" element={<PairsLayout />}>
            <Route index element={<PairsResearchPage />} />
            <Route path="discover" element={<PairsDiscoverPage />} />
            <Route path="portfolio" element={<PairsPortfolioPage />} />
          </Route>
          <Route path="guide" element={<GuidePage />} />
          <Route path="guide/:key" element={<StrategyDetailPage />} />
          <Route path="*" element={<Navigate to="/compare" replace />} />
        </Route>
      </Route>
    </Routes>
  )
}

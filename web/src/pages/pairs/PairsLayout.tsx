import { Outlet } from 'react-router'
import { PageBody, PageHeader } from '@/components/shell/PageHeader'
import { RouteTabs } from '@/components/ui/Tabs'

export default function PairsLayout() {
  return (
    <>
      <PageHeader
        title="Pairs trading"
        description="Market-neutral relative value: when two related prices diverge, buy the cheap leg, short the rich one and wait for convergence. Expect small, cost-sensitive edges in liquid large caps."
        tabs={
          <RouteTabs
            label="Pairs workflow"
            tabs={[
              { to: '/pairs', label: 'Research', end: true },
              { to: '/pairs/discover', label: 'Discover' },
              { to: '/pairs/portfolio', label: 'Portfolio' },
            ]}
          />
        }
      />
      <PageBody>
        <Outlet />
      </PageBody>
    </>
  )
}

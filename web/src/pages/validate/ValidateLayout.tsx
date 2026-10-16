import { Outlet } from 'react-router'
import { PageBody, PageHeader } from '@/components/shell/PageHeader'
import { OutOfSampleBadge } from '@/components/ui/Badge'
import { RouteTabs } from '@/components/ui/Tabs'

export default function ValidateLayout() {
  return (
    <>
      <PageHeader
        title="Validate"
        description="Optimization says what worked on the data used to choose it. Validation asks what happened next: parameters are selected on earlier observations and frozen before the unseen period is scored."
        badges={<OutOfSampleBadge />}
        tabs={
          <RouteTabs
            label="Validation method"
            tabs={[
              { to: '/validate', label: 'Single split', end: true },
              { to: '/validate/walk-forward', label: 'Walk-forward' },
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

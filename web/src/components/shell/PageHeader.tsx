import type { ReactNode } from 'react'

export function PageHeader({
  title,
  description,
  badges,
  tabs,
}: {
  title: string
  description: ReactNode
  badges?: ReactNode
  tabs?: ReactNode
}) {
  return (
    <div className="border-b border-line bg-surface/40">
      <div className="mx-auto max-w-[1600px] px-4 pt-6 sm:px-6 lg:px-8 lg:pt-8">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">{title}</h1>
          {badges}
        </div>
        <p className="mt-1 max-w-3xl text-sm leading-relaxed text-muted">{description}</p>
        {tabs ? <div className="mt-4">{tabs}</div> : <div className="h-5" />}
      </div>
    </div>
  )
}

export function PageBody({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-[1600px] px-4 py-5 sm:px-6 lg:px-8 lg:py-6">{children}</div>
}

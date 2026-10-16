// A handful of 16px stroke icons (no icon dependency needed).

import type { SVGProps } from 'react'

const PATHS = {
  compare: 'M3 13V8m4 5V4m4 9V6m4 7V9',
  backtest: 'M2 12.5 6 8l3 3 5-6.5M10.5 4.5H14V8',
  optimize:
    'M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4M10.5 8a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0Z',
  validate:
    'M8 1.8 2.8 4v3.6c0 3.1 2.2 5.6 5.2 6.6 3-1 5.2-3.5 5.2-6.6V4L8 1.8ZM5.6 8l1.7 1.7 3.2-3.4',
  pairs: 'M2.5 10.5c2-5 4-5 5.5-2.5s3.5 2.5 5.5-2.5M2.5 5.5c2 5 4 5 5.5 2.5',
  guide: 'M3 2.5h7.5a2 2 0 0 1 2 2v9H5a2 2 0 0 1-2-2v-9Zm0 9a2 2 0 0 1 2-2h7.5M6 5.5h4',
  sun: 'M8 1.5v1.5M8 13v1.5M1.5 8H3M13 8h1.5M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1M10.8 8a2.8 2.8 0 1 1-5.6 0 2.8 2.8 0 0 1 5.6 0Z',
  moon: 'M13.5 9.6A5.6 5.6 0 0 1 6.4 2.5a5.6 5.6 0 1 0 7.1 7.1Z',
  menu: 'M2.5 4.5h11M2.5 8h11M2.5 11.5h11',
  close: 'M3.5 3.5l9 9m0-9-9 9',
  play: 'M5 3.2v9.6L12.5 8 5 3.2Z',
  alert:
    'M8 5.5v3M8 10.8v.2M7.1 2.3 1.6 11.8a1 1 0 0 0 .9 1.5h11a1 1 0 0 0 .9-1.5L8.9 2.3a1 1 0 0 0-1.8 0Z',
  info: 'M8 7.2V11M8 5v.2M14.5 8a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0Z',
  refresh:
    'M13.5 3v3.5H10M2.5 13V9.5H6M3.3 6.2a5 5 0 0 1 9.2-1.4l1 1.7M12.7 9.8a5 5 0 0 1-9.2 1.4l-1-1.7',
  search: 'M7 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm7 2-3.5-3.5',
  chevronDown: 'm4 6 4 4 4-4',
  chevronUp: 'm4 10 4-4 4 4',
  arrowLeft: 'M13 8H3m4-4L3 8l4 4',
  arrowRight: 'M3 8h10M9 4l4 4-4 4',
  sort: 'm5 6 3-3 3 3M5 10l3 3 3-3',
  check: 'm3.5 8.5 3 3 6-7',
  flask:
    'M6 1.8h4M6.5 1.8v4.4L2.7 12.6a1.1 1.1 0 0 0 1 1.6h8.6a1.1 1.1 0 0 0 1-1.6L9.5 6.2V1.8M4.6 9.5h6.8',
} as const

export type IconName = keyof typeof PATHS

export function Icon({
  name,
  size = 16,
  ...props
}: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      <path d={PATHS[name]} />
    </svg>
  )
}

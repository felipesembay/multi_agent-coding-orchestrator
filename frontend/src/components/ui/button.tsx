import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'
// shadcn/ui pattern: owned source, Radix composition and CVA variants.
const variants = cva('button', {
  variants: {
    variant: {
      default: 'button-primary',
      outline: 'button-outline',
      ghost: 'button-ghost',
    },
    size: { default: '', sm: 'button-sm', icon: 'button-icon' },
  },
  defaultVariants: { variant: 'outline', size: 'default' },
})
type Props = React.ComponentProps<'button'> &
  VariantProps<typeof variants> & { asChild?: boolean }
export function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: Props) {
  const Component = asChild ? Slot : 'button'
  return (
    <Component
      className={cn(variants({ variant, size }), className)}
      {...props}
    />
  )
}

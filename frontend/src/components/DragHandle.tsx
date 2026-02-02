import { GripVertical } from 'lucide-react'
import { cn } from '@/lib/utils'
import { forwardRef } from 'react'

interface DragHandleProps extends React.HTMLAttributes<HTMLDivElement> {
  isHovered?: boolean
}

export const DragHandle = forwardRef<HTMLDivElement, DragHandleProps>(
  ({ isHovered, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "flex items-center justify-center w-6 h-full transition-opacity cursor-grab active:cursor-grabbing touch-none",
          isHovered ? "opacity-30 hover:opacity-60" : "opacity-0",
          className
        )}
        {...props}
      >
        <GripVertical className="w-4 h-4" />
      </div>
    )
  }
)

DragHandle.displayName = 'DragHandle'
import { ChevronLeft, ChevronRight, CalendarIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import { format, subDays, addDays, startOfWeek, endOfWeek, startOfMonth, subWeeks, addWeeks, subMonths, addMonths, isAfter, isBefore, isSameDay } from 'date-fns'
import { useState } from 'react'

type LeaderboardTab = 'today' | 'yesterday' | 'weekly' | 'monthly'

interface LeaderboardDatePickerProps {
  activeTab: LeaderboardTab
  selectedDate: Date
  onDateChange: (date: Date) => void
}

function formatDateForTab(date: Date, tab: LeaderboardTab): string {
  switch (tab) {
    case 'today':
    case 'yesterday':
      return format(date, 'MMM d, yyyy')
    case 'weekly': {
      const weekStart = startOfWeek(date, { weekStartsOn: 1 })
      const weekEnd = endOfWeek(date, { weekStartsOn: 1 })
      return `${format(weekStart, 'MMM d')} - ${format(weekEnd, 'MMM d, yyyy')}`
    }
    case 'monthly':
      return format(date, 'MMMM yyyy')
    default:
      return format(date, 'MMM d, yyyy')
  }
}

function navigateDate(date: Date, tab: LeaderboardTab, direction: 'prev' | 'next'): Date {
  const delta = direction === 'prev' ? -1 : 1

  switch (tab) {
    case 'today':
    case 'yesterday':
      return direction === 'prev' ? subDays(date, 1) : addDays(date, 1)
    case 'weekly':
      return direction === 'prev' ? subWeeks(date, 1) : addWeeks(date, 1)
    case 'monthly':
      return direction === 'prev' ? subMonths(date, 1) : addMonths(date, 1)
    default:
      return date
  }
}

function snapToTabBoundary(date: Date, tab: LeaderboardTab): Date {
  switch (tab) {
    case 'weekly':
      return startOfWeek(date, { weekStartsOn: 1 })
    case 'monthly':
      return startOfMonth(date)
    default:
      return date
  }
}

export function LeaderboardDatePicker({ activeTab, selectedDate, onDateChange }: LeaderboardDatePickerProps) {
  const [open, setOpen] = useState(false)
  const today = new Date()

  const canGoNext = isBefore(selectedDate, today) && !isSameDay(selectedDate, today)

  const handlePrev = () => {
    onDateChange(navigateDate(selectedDate, activeTab, 'prev'))
  }

  const handleNext = () => {
    if (canGoNext) {
      onDateChange(navigateDate(selectedDate, activeTab, 'next'))
    }
  }

  const handleCalendarSelect = (date: Date | undefined) => {
    if (date) {
      const snapped = snapToTabBoundary(date, activeTab)
      onDateChange(snapped)
      setOpen(false)
    }
  }

  return (
    <div className="flex items-center gap-1">
      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={handlePrev}
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="sm" className="gap-1.5 text-xs font-normal h-7 px-2">
            <CalendarIcon className="h-3.5 w-3.5" />
            {formatDateForTab(selectedDate, activeTab)}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="center">
          <Calendar
            mode="single"
            selected={selectedDate}
            onSelect={handleCalendarSelect}
            disabled={(date) => isAfter(date, today)}
            initialFocus
          />
        </PopoverContent>
      </Popover>

      <Button
        variant="ghost"
        size="icon"
        className="h-7 w-7"
        onClick={handleNext}
        disabled={!canGoNext}
      >
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  )
}

import { useState, useRef, useEffect } from 'react'
import { ChevronDown, Plus, GripVertical } from 'lucide-react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { Section } from '@/types/projects'
import { useUpdateSection } from '@/hooks/useSections'

interface SectionHeaderProps {
  section: Section
  isExpanded?: boolean
  onToggleExpand?: () => void
  onAddSection?: () => void
  autoFocus?: boolean
  onAutoFocusHandled?: () => void
  onDragStart?: (startX: number, startY: number) => void
  isDragging?: boolean
  isOverlay?: boolean
}

export function SectionHeader({
  section,
  isExpanded = true,
  onToggleExpand,
  onAddSection,
  autoFocus,
  onAutoFocusHandled,
  onDragStart,
  isDragging,
  isOverlay
}: SectionHeaderProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [isHovered, setIsHovered] = useState(false)
  const [name, setName] = useState(section.name)
  const inputRef = useRef<HTMLInputElement>(null)
  const shouldSelectAllRef = useRef(false)
  const updateSection = useUpdateSection()

  useEffect(() => {
    setName(section.name)
  }, [section.name])

  useEffect(() => {
    if (autoFocus && !isEditing) {
      shouldSelectAllRef.current = true
      setIsEditing(true)
      onAutoFocusHandled?.()
    }
  }, [autoFocus, isEditing, onAutoFocusHandled])

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      if (shouldSelectAllRef.current) {
        // Select all text for newly created sections
        inputRef.current.select()
        shouldSelectAllRef.current = false
      } else {
        // Move cursor to end of text for user clicks
        const len = inputRef.current.value.length
        inputRef.current.setSelectionRange(len, len)
      }
    }
  }, [isEditing])

  const handleNameClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setIsEditing(true)
  }

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setName(e.target.value)
  }

  const handleNameBlur = () => {
    if (name !== section.name && name.trim()) {
      updateSection.mutate({
        sectionId: section.id,
        data: { name: name.trim() }
      })
    } else {
      setName(section.name)
    }
    setIsEditing(false)
  }

  const handleNameKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleNameBlur()
    } else if (e.key === 'Escape') {
      setName(section.name)
      setIsEditing(false)
    }
  }

  const handleAddSectionClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onAddSection?.()
  }

  const handleDragHandleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onDragStart?.(e.clientX, e.clientY)
  }

  return (
    <div
      className={cn(
        "group flex items-center gap-2 px-2 py-3 cursor-pointer transition-colors relative",
        !isEditing && "hover:bg-accent/50",
        "bg-card",
        isOverlay && "shadow-xl border-2 border-primary rounded-md",
        isDragging && "opacity-30 bg-accent/50"
      )}
      onClick={() => onToggleExpand?.()}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Drag Handle */}
      {!isOverlay && (
        <div
          data-drag-handle
          onMouseDown={handleDragHandleMouseDown}
          className={cn(
            "flex items-center justify-center w-6 transition-opacity cursor-grab active:cursor-grabbing",
            isHovered ? "opacity-50 hover:opacity-100" : "opacity-0"
          )}
        >
          <GripVertical className="w-4 h-4" />
        </div>
      )}

      {/* Expand/Collapse Button */}
      <button
        className="flex items-center justify-center w-6 h-6 -m-1 rounded hover:bg-accent transition-colors cursor-pointer"
        onClick={(e) => {
          e.stopPropagation()
          onToggleExpand?.()
        }}
      >
        <motion.div
          animate={{ rotate: isExpanded ? 0 : -90 }}
          transition={{ duration: 0.15 }}
        >
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        </motion.div>
      </button>

      {/* Section Name */}
      <div className="flex items-center gap-1">
        {isEditing ? (
          <input
            ref={inputRef}
            type="text"
            value={name}
            onChange={handleNameChange}
            onBlur={handleNameBlur}
            onKeyDown={handleNameKeyDown}
            onClick={(e) => e.stopPropagation()}
            className="px-1 py-0.5 text-base font-semibold outline-none bg-background cursor-text rounded ring-2 ring-primary"
          />
        ) : (
          <div
            onClick={handleNameClick}
            className="px-1 py-0.5 text-base font-semibold cursor-text rounded hover:ring-1 hover:ring-border"
          >
            {name}
          </div>
        )}

        {/* Add Section Button - directly next to name */}
        {onAddSection && (
          <button
            onClick={handleAddSectionClick}
            className={cn(
              "p-1 rounded transition-all cursor-pointer",
              "opacity-0 group-hover:opacity-100",
              "hover:bg-accent"
            )}
            title="Add section below"
          >
            <Plus className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Spacer to push content left */}
      <div className="flex-1" />
    </div>
  )
}
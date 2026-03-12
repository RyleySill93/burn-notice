export const FLAME_WAR_USER_IDS = ['user-6yckeUKu1M9nH', 'user-pxSgASZi41Zq']

export function hasFlameWarAccess(userId: string | undefined): boolean {
  return !!userId && FLAME_WAR_USER_IDS.includes(userId)
}

import { View } from 'react-native';
import { appearance as visual } from './theme';

export function SkeletonBlock({ width = '100%', height = 22 }: { width?: number | `${number}%`; height?: number }) {
  return <View style={{ width, height, borderRadius: 10, backgroundColor: visual.border, opacity: 0.45 }} />;
}
export function LoadingSkeleton({ label = '경기 기록 불러오는 중', rows = 3 }: { label?: string; rows?: number }) {
  return <View accessible accessibilityLabel={label} accessibilityState={{ busy: true }} style={{ gap: 16 }}>
    <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ gap: 16 }}>
      {Array.from({ length: rows }, (_, index) => <View key={index} style={{ padding: 20, gap: 16, borderRadius: 20, backgroundColor: visual.surface }}>
        <SkeletonBlock width="40%" height={16} />
        <SkeletonBlock width="85%" height={28} />
        <SkeletonBlock width="60%" />
        <SkeletonBlock height={48} />
      </View>)}
    </View>
  </View>;
}

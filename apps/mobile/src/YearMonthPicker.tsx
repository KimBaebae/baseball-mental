import { Pressable, Text, View } from 'react-native';
import { colors, s } from './ui';

export function YearMonthPicker({ year, month, onChange, allowAll = false }: {
  year: number;
  month: number | null;
  onChange: (year: number, month: number | null) => void;
  allowAll?: boolean;
}) {
  const choice = (label: string, selected: boolean, onPress: () => void) => <Pressable
    key={label} accessibilityRole="button" accessibilityLabel={label}
    accessibilityState={{ selected }} onPress={onPress}
    style={{ minWidth: 68, minHeight: 48, paddingHorizontal: 16, paddingVertical: 13, borderRadius: 999, borderWidth: 1, borderColor: colors.line, backgroundColor: selected ? colors.primary : colors.bg, alignItems: 'center' }}>
    <Text style={{ color: selected ? colors.onPrimary : colors.ink, fontWeight: '700' }}>{selected ? '✓ ' : ''}{label}</Text>
  </Pressable>;
  return <View style={{ gap: 12 }}>
    <Text style={s.heading}>연도 선택</Text>
    <View style={{ flexDirection: 'row', gap: 8 }}>
      {[2026].map(value => choice(`${value}년`, year === value, () => onChange(value, month)))}
    </View>
    <Text style={s.body}>현재 2026년 기록을 제공해요.</Text>
    <Text style={s.heading}>월 선택</Text>
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
      {allowAll ? choice('전체 월', month === null, () => onChange(year, null)) : null}
      {Array.from({ length: 12 }, (_, index) => index + 1).map(value => choice(`${value}월`, month === value, () => onChange(year, value)))}
    </View>
  </View>;
}

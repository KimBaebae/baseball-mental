export type TeamPalette = { accent: string; soft: string; surface: string; secondary: string; border: string };

// Product palettes inspired by team identities; not official club color specifications.
export const teamPalettes: Record<string, TeamPalette> = {
  LG: { accent: '#FF5D85', soft: '#15141D', surface: '#292031', secondary: '#F5F7FF', border: '#B93860' },
  OB: { accent: '#9EB9EE', soft: '#101626', surface: '#1B2943', secondary: '#EE4E5A', border: '#526B9E' },
  KT: { accent: '#F35B64', soft: '#18171C', surface: '#2C232B', secondary: '#F7F9FF', border: '#9D454E' },
  SS: { accent: '#66A7FF', soft: '#0E192C', surface: '#192E4D', secondary: '#F7F9FF', border: '#376DB2' },
  HH: { accent: '#FF963C', soft: '#1D1715', surface: '#33271F', secondary: '#F7F9FF', border: '#AC642D' },
  HT: { accent: '#FF5967', soft: '#20151B', surface: '#39222D', secondary: '#F7F9FF', border: '#B34150' },
  LT: { accent: '#FF7975', soft: '#101C29', surface: '#1D3144', secondary: '#8BBCE1', border: '#3D6383' },
  NC: { accent: '#80B5E8', soft: '#111D2C', surface: '#20334B', secondary: '#DDB879', border: '#58799B' },
  SK: { accent: '#FA596A', soft: '#21151C', surface: '#38232F', secondary: '#E8C68A', border: '#A23B50' },
  WO: { accent: '#D99BC8', soft: '#21131F', surface: '#382237', secondary: '#F7F9FF', border: '#92517E' },
};
export const neutralPalette: TeamPalette = { accent: '#8CB4FF', soft: '#101522', surface: '#1B2334', secondary: '#F7F9FF', border: '#39445A' };

/** Ilustrasi pengeboran (login): rig + derrick, lapisan formasi, sumur berarah dengan casing, drill string & bit,
 *  sirkulasi lumpur (turun di dalam string, naik di annulus), dan kartu mini ECD di antara batas PP/SFG–FG. */
export function DrillingScene() {
  return (
    <svg className="scene" viewBox="0 0 900 1000" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#CFE3F7" /><stop offset="1" stopColor="#F2F7FC" />
        </linearGradient>
        <pattern id="sand" width="14" height="14" patternUnits="userSpaceOnUse">
          <rect width="14" height="14" fill="#E4CD98" /><circle cx="3" cy="4" r="1.1" fill="#C9AE72" /><circle cx="10" cy="10" r="1" fill="#C9AE72" />
        </pattern>
        <pattern id="shale" width="40" height="10" patternUnits="userSpaceOnUse">
          <rect width="40" height="10" fill="#A99C92" /><path d="M0 5h18M24 5h12" stroke="#8E8178" strokeWidth="1.2" />
        </pattern>
        <pattern id="lime" width="36" height="18" patternUnits="userSpaceOnUse">
          <rect width="36" height="18" fill="#D6CEBD" /><path d="M0 0h36M0 9h36M9 0v9M27 9v9" stroke="#BDB3A0" strokeWidth="1" />
        </pattern>
        <pattern id="res" width="16" height="16" patternUnits="userSpaceOnUse">
          <rect width="16" height="16" fill="#D8B46E" /><circle cx="4" cy="5" r="1.3" fill="#B48E45" /><circle cx="12" cy="12" r="1.2" fill="#8C6B2E" />
        </pattern>
        <linearGradient id="steel" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#5E6B79" /><stop offset=".5" stopColor="#9AA7B5" /><stop offset="1" stopColor="#5E6B79" />
        </linearGradient>
      </defs>

      {/* langit & bukit jauh */}
      <rect width="900" height="432" fill="url(#sky)" />
      <circle cx="140" cy="300" r="46" fill="#FFF3D6" opacity=".9" />
      <path d="M0 400 Q120 352 260 392 T520 380 T900 372 V432 H0Z" fill="#C7D9C1" />
      <path d="M0 418 Q180 392 360 414 T720 404 T900 410 V432 H0Z" fill="#AFC8A6" />

      {/* lapisan formasi */}
      <rect y="430" width="900" height="70" fill="#B9926A" />
      <rect y="500" width="900" height="120" fill="url(#sand)" />
      <rect y="620" width="900" height="120" fill="url(#shale)" />
      <rect y="740" width="900" height="110" fill="url(#lime)" />
      <rect y="850" width="900" height="150" fill="url(#res)" />
      <g fill="#5A4632" fontSize="13" fontFamily="Inter, sans-serif" opacity=".75">
        <text x="400" y="560">batupasir</text>
        <text x="400" y="684">serpih (shale)</text>
        <text x="400" y="800">batugamping</text>
        <text x="640" y="960">reservoir</text>
      </g>

      {/* lubang sumur: vertikal → build → horizontal */}
      <path d="M560 430 V690 Q560 900 760 905 H900" fill="none" stroke="#5B4A3B" strokeWidth="22" strokeLinecap="round" opacity=".85" />
      {/* casing sampai shoe */}
      <path d="M548 430 V610 M572 430 V610" stroke="url(#steel)" strokeWidth="4" />
      <path d="M543 610 l5 -10 v10z M577 610 l-5 -10 v10z" fill="#5E6B79" />
      <text x="584" y="614" fontSize="12" fill="#2E2219" fontFamily="Inter, sans-serif">casing shoe</text>
      {/* drill string */}
      <path d="M560 300 V690 Q560 892 742 897" fill="none" stroke="#2E3A47" strokeWidth="5" />
      {/* mud: turun di dalam string */}
      <path className="mud-down" d="M560 300 V690 Q560 892 742 897" fill="none" stroke="#F59A3C" strokeWidth="2.2" strokeDasharray="7 10" />
      {/* mud: naik di annulus */}
      <path className="mud-up" d="M742 905 Q552 904 552 690 V432" fill="none" stroke="#4C8FE0" strokeWidth="2.2" strokeDasharray="7 10" />
      {/* bit PDC */}
      <g transform="translate(748 897)">
        <circle r="11" fill="#E8710A" stroke="#7A3A05" strokeWidth="2" />
        <path d="M11 0 l6 -4 v8z M0 -11 l-3 -6 h6z M0 11 l-3 6 h6z" fill="#7A3A05" />
      </g>

      {/* rig: substructure & lantai bor */}
      <rect x="470" y="392" width="180" height="40" fill="#3D4B5C" />
      <path d="M470 432 l20 -40 M500 432 l20 -40 M530 432 l20 -40 M590 432 l20 -40 M620 432 l20 -40" stroke="#5E6E80" strokeWidth="3" />
      <rect x="462" y="384" width="196" height="10" fill="#26323F" />
      {/* derrick */}
      <g stroke="#C2410C" strokeWidth="4" fill="none" strokeLinejoin="round">
        <path d="M508 384 L548 120 M612 384 L572 120 M548 120 H572" />
        <path d="M513 352 H607 M520 306 H600 M527 260 H593 M534 214 H586 M541 168 H579" strokeWidth="2.5" />
        <path d="M513 352 L600 306 M607 352 L520 306 M520 306 L593 260 M600 306 L527 260 M527 260 L586 214 M593 260 L534 214 M534 214 L579 168 M586 214 L541 168" strokeWidth="1.8" />
      </g>
      <rect x="542" y="104" width="36" height="16" rx="3" fill="#26323F" />
      <path d="M560 120 V200" stroke="#26323F" strokeWidth="1.6" />
      <rect x="548" y="200" width="24" height="30" rx="4" fill="#F2B233" stroke="#8A5A00" strokeWidth="2" />
      <rect x="552" y="230" width="16" height="22" fill="#4B5866" />
      <path d="M560 252 V384" stroke="#2E3A47" strokeWidth="5" />
      {/* doghouse */}
      <rect x="402" y="350" width="62" height="42" rx="3" fill="#E9EEF3" stroke="#3D4B5C" strokeWidth="2" />
      <rect x="414" y="360" width="16" height="12" fill="#9CC3EA" /><rect x="436" y="360" width="16" height="12" fill="#9CC3EA" />
      {/* mud tank + pompa + standpipe */}
      <rect x="676" y="372" width="120" height="44" rx="3" fill="#2F6FD1" opacity=".9" />
      <rect x="684" y="364" width="36" height="10" fill="#1F5FAE" /><rect x="740" y="364" width="36" height="10" fill="#1F5FAE" />
      <rect x="806" y="386" width="58" height="30" rx="4" fill="#4B5866" />
      <circle cx="822" cy="420" r="5" fill="#26323F" /><circle cx="848" cy="420" r="5" fill="#26323F" />
      <path d="M806 400 H786 M676 400 H640 V300 H572" fill="none" stroke="#2E3A47" strokeWidth="3" />
      {/* pipe rack */}
      <g stroke="#7B8794" strokeWidth="4" strokeLinecap="round">
        <path d="M300 410 H440 M304 418 H444 M308 426 H448" />
      </g>

      {/* kartu mini ECD: ECD ⓥ di antara PP/SFG dan FG */}
      <g transform="translate(90 748)">
        <rect width="300" height="176" rx="12" fill="#fff" opacity=".93" stroke="#D5DCE4" />
        <text x="16" y="26" fontSize="13" fontWeight="600" fill="#1B2430" fontFamily="Inter, sans-serif">ECD ⓥ vs jendela tekanan</text>
        <path d="M16 54 H284" stroke="#D63A40" strokeWidth="2" strokeDasharray="6 4" />
        <text x="284" y="48" textAnchor="end" fontSize="11" fill="#D63A40" fontFamily="Inter, sans-serif">FG min</text>
        <path d="M16 146 H284" stroke="#B98900" strokeWidth="2" strokeDasharray="6 4" />
        <text x="284" y="162" textAnchor="end" fontSize="11" fill="#8A6700" fontFamily="Inter, sans-serif">max(PP, SFG)</text>
        <path d="M16 124 H284" stroke="#2F6FD1" strokeWidth="1.5" />
        <text x="20" y="118" fontSize="11" fill="#2F6FD1" fontFamily="Inter, sans-serif">MW</text>
        <path d="M16 106 C46 104 62 100 84 101 S126 96 148 92 S182 84 200 86 S236 70 254 74 L284 70" fill="none" stroke="#E8710A" strokeWidth="3" />
        <path d="M16 96 C62 90 126 86 200 76 S260 60 284 60 L284 82 C252 86 222 98 200 96 S126 106 16 116 Z" fill="#E8710A" opacity=".12" />
        <circle cx="284" cy="70" r="4" fill="#E8710A" />
        <text x="150" y="80" fontSize="11" fill="#B4560A" fontFamily="Inter, sans-serif">ECD ⓥ</text>
      </g>
    </svg>
  );
}

/** Ikon kecil derrick untuk brand. */
export function RigIcon({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="#E8710A" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M8 21 L11 3 H13 L16 21" /><path d="M9 15 H15 M10 9 H14 M9 15 L14 9 M15 15 L10 9" />
      <path d="M5 21 H19" stroke="#1F5FAE" /><path d="M12 21 V23" stroke="#1F5FAE" />
    </svg>
  );
}

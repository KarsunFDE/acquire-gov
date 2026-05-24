import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { FIXTURE_VENDORS } from '../../services/mock-fixtures';

/**
 * Vendor Directory (CO / CS / evaluator / PM).
 *
 * SAM.gov entity-style fields: DUNS, UEI, CAGE, NAICS codes, set-asides.
 * Past-performance rollup shown inline.
 */
@Component({
  selector: 'app-vendor-directory',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Vendor directory</h2>
        <div class="subtitle">SAM.gov entity-style fields · CPARS rollup</div>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>Vendor</th><th>DUNS / UEI / CAGE</th><th>NAICS</th><th>Set-asides</th><th>CPARs (Exc/VG/Sat/Marg/Unsat)</th>
        </tr>
      </thead>
      <tbody>
        <tr *ngFor="let v of vendors">
          <td><a [routerLink]="['/vendors', v.id]"><strong>{{ v.name }}</strong></a></td>
          <td>
            <div style="font-family:monospace;font-size:0.8rem">
              {{ v.duns }}<br>{{ v.uei }}<br>{{ v.cage }}
            </div>
          </td>
          <td>{{ v.naicsCodes.join(', ') }}</td>
          <td>{{ v.setAsides.join(', ') }}</td>
          <td>
            <span class="badge exceptional">{{ v.pastPerformanceAvg.exceptional }}</span>
            <span class="badge very_good">{{ v.pastPerformanceAvg.veryGood }}</span>
            <span class="badge satisfactory">{{ v.pastPerformanceAvg.satisfactory }}</span>
            <span class="badge marginal">{{ v.pastPerformanceAvg.marginal }}</span>
            <span class="badge unsatisfactory">{{ v.pastPerformanceAvg.unsatisfactory }}</span>
          </td>
        </tr>
      </tbody>
    </table>
  `,
})
export class VendorDirectoryComponent {
  vendors = FIXTURE_VENDORS;
}

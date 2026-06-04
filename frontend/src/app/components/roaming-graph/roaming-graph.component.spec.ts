import { ComponentFixture, TestBed } from '@angular/core/testing';

import { RoamingGraphComponent } from './roaming-graph.component';

describe('RoamingGraphComponent', () => {
  let component: RoamingGraphComponent;
  let fixture: ComponentFixture<RoamingGraphComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [RoamingGraphComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(RoamingGraphComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

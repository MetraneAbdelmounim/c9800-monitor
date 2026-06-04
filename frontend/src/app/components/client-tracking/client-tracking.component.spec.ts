import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ClientTrackingComponent } from './client-tracking.component';

describe('ClientTrackingComponent', () => {
  let component: ClientTrackingComponent;
  let fixture: ComponentFixture<ClientTrackingComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ClientTrackingComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(ClientTrackingComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});



